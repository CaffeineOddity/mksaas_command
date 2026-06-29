"""mksaas.prompts — 通用环境分组采集交互。

docs/env-groups/*.md §5 为采集流程模板；REQUIREMENTS §3.3 为交互确认顺序。
依赖 Console 缝与 schema。collect_group：采集指定 profile，每行变量预填当前值/
schema 默认值，留空=保留。敏感字段走 getpass。database 分组走提供商选择引导。
"""

from __future__ import annotations

import re
import webbrowser
from typing import Any, Dict

from mksaas.console import Console
from mksaas.masking import mask
from mksaas.schema import find_group
from mksaas.secrets_gen import gen_better_auth_secret

# 视为 URL 的变量名（采集时校验 http/https）
_URL_VARS = {"NEXT_PUBLIC_BASE_URL"}

_URL_RE = re.compile(r"^https?://[^\s]+$")

# database 提供商：名称 → 官网（采集时打开，引导用户创建项目）
_DB_PROVIDERS = {
    "Neon": "https://neon.com/",
    "Supabase": "https://supabase.com/",
}

# payment 提供商：名称 → 官网 / webhook 路径 / 该提供商需采集的变量 / provider 开关值 / 创建步骤
# 选定后仅采集该提供商变量，VITE_PAYMENT_PROVIDER 自动写入。
_PAYMENT_PROVIDERS = {
    "Stripe": {
        "url": "https://dashboard.stripe.com/",
        "webhook_path": "/api/webhooks/stripe",
        "provider_value": "stripe",
        "vars": [
            "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
            "NEXT_PUBLIC_STRIPE_PRICE_PRO_MONTHLY",
            "NEXT_PUBLIC_STRIPE_PRICE_PRO_YEARLY",
            "NEXT_PUBLIC_STRIPE_PRICE_LIFETIME",
            "NEXT_PUBLIC_STRIPE_PRICE_CREDITS_BASIC",
            "NEXT_PUBLIC_STRIPE_PRICE_CREDITS_STANDARD",
            "NEXT_PUBLIC_STRIPE_PRICE_CREDITS_PREMIUM",
            "NEXT_PUBLIC_STRIPE_PRICE_CREDITS_ENTERPRISE",
        ],
        "guide": lambda base: [
            "在 stripe.com 创建 Stripe 账户",
            f"1. 左下角Developers > API 密钥 -> 复制“密钥”，即私钥（测试 sk_test_ / 生产 sk_live_ 开头）→ STRIPE_SECRET_KEY",
            f"2. 左下角Developers > Webhooks > 添加接收端 > 'your account' > 添加‘事件’ ",
            "监听 invoice.paid / checkout.session.completed / customer.subscription.created/updated/deleted > 继续",
            f"正式环境：Webhook端点 > 目标名称: 填你项目名 > 端点 URL 填: {_callback(base, '/api/webhooks/stripe')}",
            "测试环境：使用stripe cli见 https://mksaas.com/zh/docs/payment/stripe#开发环境",
            "Reveal 拿签名密钥（whsec_ 开头）→ STRIPE_WEBHOOK_SECRET",
            "3. Product Catalog 创建「专业版计划」产品，加月度($9.90/月)与年度($99.00/年)定期价格，",
            "复制 price_ ID → NEXT_PUBLIC_STRIPE_PRICE_PRO_MONTHLY / _PRO_YEARLY",
            "创建「终身计划」产品，一次性价格 $199.00，复制 price_ ID → NEXT_PUBLIC_STRIPE_PRICE_LIFETIME",
            "（可选）按需创建 credits 价格 → NEXT_PUBLIC_STRIPE_PRICE_CREDITS_*",
        ],
    },
    "Creem": {
        "url": "https://creem.io/",
        "webhook_path": "/api/webhooks/creem",
        "provider_value": "creem",
        "vars": [
            "CREEM_API_KEY", "CREEM_WEBHOOK_SECRET",
            "VITE_CREEM_PRODUCT_PRO_MONTHLY",
            "VITE_CREEM_PRODUCT_PRO_YEARLY",
            "VITE_CREEM_PRODUCT_LIFETIME", 
        ],
        "guide": lambda base: [
            "在 creem.io 创建 Creem 账户（无需信用卡）",
            "Developers 复制 API 密钥（测试 creem_test_ / 生产 creem_live_ 开头）→ CREEM_API_KEY",
            f"Developers > Webhooks 添加 URL {_callback(base, '/api/webhooks/creem')}，复制签名密钥 → CREEM_WEBHOOK_SECRET",
            "Products 创建「Pro Plan」月度产品（recurring / every-month）→ VITE_CREEM_PRODUCT_PRO_MONTHLY",
            "创建年度产品（recurring / every-year）→ VITE_CREEM_PRODUCT_PRO_YEARLY",
            "创建「Lifetime Plan」一次性产品（one_time）→ VITE_CREEM_PRODUCT_LIFETIME",
        ],
    },
}

# 需引导的分组：group_id → 申请地址 / 创建步骤引导
# 进入采集时自动打开申请地址，并按平台打印各自创建步骤。
# OAuth 分组的引导会按 base_url 计算回调 URL；email 等无需回调。
_GUIDED_GROUPS = {
    "github_oauth": {
        "apply_url": "https://github.com/settings/applications/new",
        "guide": lambda base: [
            "Application name",
            "Homepage URL",
            f"创建应用时请将回调 URL（Authorization callback URL）填为：{_callback(base, '/api/auth/callback/github')}",
        ],
    },
    "google_oauth": {
        "apply_url": "https://console.cloud.google.com/apis/credentials",
        "guide": lambda base: [
            "创建项目（左上角）",
            "创建凭据（顶部）→ 选择「OAuth 客户端」",
            "应用类型：Web 应用程序",
            "名称：自定义应用名",
            f"已获授权的 JavaScript 来源：{base or '<base_url>'}",
            f"已获授权的重定向 URI（回调 URL）：{_callback(base, '/api/auth/callback/google')}",
            "点击创建，拿到 Client ID / Secret",
        ],
    },
    "email": {
        "apply_url": "https://resend.com/onboarding",
        "guide": lambda base: [
            "在 onboarding 页面完成账号注册 / 登录",
            "进入左侧 API Keys 页面（或直接访问 https://resend.com/api-keys）",
            "点击 Create API Key 生成密钥",
            "复制密钥后回填到下方 RESEND_API_KEY",
        ],
    },
    "storage": {
        "apply_url": "https://dash.cloudflare.com/?to=/:account/r2",
        "guide": lambda base: [
            "1. 在 cloudflare.com 注册 / 登录 Cloudflare 账户",
            "2. R2 对象存储 → 创建存储桶：选择全局唯一的存储桶名称（如 your-project-name），选择靠近目标受众的区域",
            "3. 进入存储桶 → Settings → Public Development URL，点击启用；将该公共访问 URL 保存为 STORAGE_PUBLIC_URL",
            "4.（推荐）为存储桶公共访问设置自定义域名，保存为 STORAGE_PUBLIC_URL 以提升安全性",
            "5. R2对象存储 → 账户详情 → 管理 → Create User API Token",
            "输入“令牌名称” → 权限选择“对象读和写” → 指定存储桶选择“仅应用于特定存储桶”→ 选择刚刚创建的“存储桶对象” -> 创建用户API令牌",
            "创建后，提取“S3 客户端”的Access Key ID 与 Secret Access Key / endpoint，记录下来就可以开始填环境",
            "6. 回到下方逐项回填：STORAGE_REGION / STORAGE_BUCKET_NAME / STORAGE_ACCESS_KEY_ID / STORAGE_SECRET_ACCESS_KEY / STORAGE_ENDPOINT / STORAGE_PUBLIC_URL",
            "STORAGE_ENDPOINT 形如 https://<account-id>.r2.cloudflarestorage.com；STORAGE_REGION 填 auto",
        ],
    },
}


def _callback(base_url: str, callback_path: str) -> str:
    """按 base_url + 回调路径拼出完整回调 URL；base_url 为空时用占位。"""
    if base_url:
        return base_url.rstrip("/") + callback_path
    return f"<base_url>{callback_path}"


def _is_url_var(name: str) -> bool:
    return name in _URL_VARS


def _existing_group(state: Dict[str, Any], group_id: str, profile: str) -> Dict[str, Any]:
    return (
        state.setdefault("profiles", {})
        .setdefault(profile, {"base_url": "", "env_groups": {}})
        .setdefault("env_groups", {})
        .get(group_id, {})
    )


def _schema_default(var: Dict[str, Any], profile: str) -> str:
    """取该变量在指定 profile 的 schema 默认值（test_default / prod_default）。"""
    key = "test_default" if profile == "test" else "prod_default"
    return var.get(key, "") or var.get("default", "")


def _current_value(var: Dict[str, Any], existing: Dict[str, Any], profile: str) -> str:
    """该变量当前值：已采集取之，否则取该 profile 的 schema 默认。"""
    field = existing.get(var["name"], {})
    val = (field.get("value") or "").strip()
    if val:
        return val
    return _schema_default(var, profile)


def _format_prompt(var: Dict[str, Any], current: str) -> str:
    """构造单变量提示行：name（描述）[标记] (当前: xxx)。"""
    name = var["name"]
    desc = var.get("description", "")
    prompt = f"  {name}"
    if desc:
        prompt += f"（{desc}）"

    tags = []
    if var.get("required"):
        tags.append("必填")
    else:
        tags.append("可选")
    if var.get("generate_if_empty"):
        tags.append("空则自动生成")
    if var.get("sensitive"):
        tags.append("隐藏输入")
    if tags:
        prompt += f" [{' / '.join(tags)}]"

    # 当前/默认值展示：敏感字段脱敏，空值用 <空>
    if var.get("sensitive") and current:
        shown = mask(current)
    else:
        shown = current or "<空>"
    prompt += f" (当前: {shown})"
    return prompt


def _collect_one(console: Console, var: Dict[str, Any], current: str) -> str:
    """采集单个变量：预填当前值，留空=保留，输入=覆盖。敏感走 getpass。

    questionary 版：TerminalConsole.input/getpass 预填 default，留空即返回 default。
    必填缺失不在采集时强制，留空即跳过，由 apply 阶段拦截；URL 校验保留。
    """
    name = var["name"]
    sensitive = bool(var.get("sensitive"))
    prompt = _format_prompt(var, current)

    while True:
        if sensitive:
            # 敏感字段：getpass 预填当前值（questionary 隐藏输入），留空返回 current
            value = console.getpass(prompt + " 留空保留", default=current)
        else:
            value = console.input(prompt + " 留空保留", default=current)
        value = (value or "").strip()

        # 留空（含 current 为空）即跳过：不在采集时强制必填，必填缺失由 apply 阶段拦截
        if not value:
            return value
        if _is_url_var(name) and not _URL_RE.match(value):
            console.print(f"  {name} 需为 http:// 或 https:// 开头的 URL")
            continue
        return value


def _collect_profile(state: Dict[str, Any], schema_group: Dict[str, Any],
                     group_id: str, profile: str, console: Console,
                     hint: str) -> Dict[str, Any]:
    """采集某 profile 的全部变量，返回写回 state 的新分组 dict。"""
    existing = _existing_group(state, group_id, profile)
    console.print(f"  ── {profile}（{hint}）──")
    new_group: Dict[str, Any] = {}
    for var in schema_group["variables"]:
        name = var["name"]
        current = _current_value(var, existing, profile)
        value = _collect_one(console, var, current)

        # BETTER_AUTH_SECRET 空 + generate_if_empty：确认是否自动生成
        if not value and var.get("generate_if_empty"):
            if console.confirm(f"  {name} 是否自动生成？", default=True):
                value = gen_better_auth_secret()
                source = "prompt_or_generate"
            else:
                source = "default"
        elif not value:
            source = "default" if _schema_default(var, profile) else "prompt"
        elif value == current and current:
            # 留空保留：source 沿用既有，无既有则按是否默认值判定
            prev_source = existing.get(name, {}).get("source")
            if prev_source:
                source = prev_source
            elif value == _schema_default(var, profile):
                source = "default"
            else:
                source = "prompt"
        else:
            source = "prompt"

        new_group[name] = {
            "value": value,
            "source": source,
            "required": bool(var.get("required")),
            "description": var.get("description", ""),
        }
        if var.get("sensitive"):
            new_group[name]["sensitive"] = True
        if var.get("generate_if_empty"):
            new_group[name]["generate_if_empty"] = True

    state["profiles"][profile]["env_groups"][group_id] = new_group
    return new_group


def collect_group(state: Dict[str, Any], group_id: str, profile: str,
                  console: Console) -> bool:
    """采集某分组的指定 profile，留空=保留，回写 state。

    profile 决定采集 test 还是 prod（init 编排器分别调用两次）。
    database 分组走提供商选择引导：选 Neon/Supabase → 打开官网 → 输入 DATABASE_URL，
    空输入确认后不写入（回到分组菜单）。
    """
    schema_group = find_group(group_id)
    summary = schema_group.get("description") or group_id
    hint = "测试环境，可用 localhost/占位值" if profile == "test" else "正式环境，请填写真实域名/密钥"

    if group_id == "database":
        if not _collect_database(state, schema_group, group_id, profile, console, hint):
            return False  # 用户空输入确认，未写入
        console.print(f"分组 {group_id}/{profile} 已采集（未应用，需在 apply 阶段统一落地）")
        return True

    if group_id == "payment":
        _collect_payment(state, schema_group, group_id, profile, console, hint)
        console.print(f"分组 {group_id}/{profile} 已采集（未应用，需在 apply 阶段统一落地）")
        return True

    if group_id in _GUIDED_GROUPS:
        _collect_guided(state, schema_group, group_id, profile, console, hint)
        console.print(f"分组 {group_id}/{profile} 已采集（未应用，需在 apply 阶段统一落地）")
        return True

    console.print(f"采集 {group_id}/{profile}（{summary}，{hint}）：每行留空=保留，输入新值=覆盖")
    _collect_profile(state, schema_group, group_id, profile, console, hint)
    console.print(f"分组 {group_id}/{profile} 已采集（未应用，需在 apply 阶段统一落地）")
    return True


def _collect_guided(state: Dict[str, Any], schema_group: Dict[str, Any],
                    group_id: str, profile: str, console: Console, hint: str) -> None:
    """需要引导的分组采集：打开申请地址 → 打印创建步骤 → 采集字段。

    适用 github_oauth / google_oauth / email 等需前往第三方平台创建凭据的分组。
    OAuth 分组的创建步骤会按当前 profile 的 NEXT_PUBLIC_BASE_URL 计算回调 URL；
    base_url 为空时以 <base_url> 占位并提示先采集 core 分组。
    """
    info = _GUIDED_GROUPS[group_id]
    apply_url = info["apply_url"]
    summary = schema_group.get("description", group_id)

    console.print(f"\n申请【{group_id}】【{profile}环境信息】")
    console.print(f"\n请在浏览器完成 {summary}，拿到所需凭据后回填：")

    open_success = False
    try:
        webbrowser.open(apply_url)
        open_success = True
    except Exception:  # noqa: BLE001 - 非交互环境打不开浏览器不致命
        console.print(f"（浏览器未自动打开，请手动访问：{apply_url}）")

    # 回调 URL：取当前 profile 的 base_url（即 NEXT_PUBLIC_BASE_URL 采集值）
    base_url = _profile_base_url(state, profile)
    if not base_url and group_id in ("github_oauth", "google_oauth"):
        console.print("提示：尚未采集 NEXT_PUBLIC_BASE_URL（core 分组），请在创建应用时按 <base_url> 自行替换实际域名")

    if open_success:
        console.print("\n创建步骤：")
        for i, step in enumerate(info["guide"](base_url), start=1):
            console.print(f"  {i}: {step}")

    _collect_profile(state, schema_group, group_id, profile, console, hint)


def _profile_base_url(state: Dict[str, Any], profile: str) -> str:
    """取当前 profile 已采集的 NEXT_PUBLIC_BASE_URL（core 分组）。"""
    core = (state.get("profiles", {}).get(profile, {})
            .get("env_groups", {}).get("core", {}))
    val = (core.get("NEXT_PUBLIC_BASE_URL", {}).get("value") or "").strip()
    return val


def _collect_database(state: Dict[str, Any], schema_group: Dict[str, Any],
                      group_id: str, profile: str, console: Console, hint: str) -> bool:
    """database 分组采集：选提供商 → 打开官网 → 输入 DATABASE_URL。

    空输入确认后返回 False（不写入，回到分组菜单）。
    """
    existing = _existing_group(state, group_id, profile)
    current = _current_value(
        next(v for v in schema_group["variables"] if v["name"] == "DATABASE_URL"),
        existing, profile)

    console.print(f"采集 {group_id}/{profile}（{schema_group.get('description', group_id)}，{hint}）")
    # 1. 选择数据库提供商
    provider_idx = console.choose("选择数据库提供商", list(_DB_PROVIDERS.keys()) + ["跳过/手动输入"],
                                  default=len(_DB_PROVIDERS) + 1)
    if provider_idx <= len(_DB_PROVIDERS):
        provider = list(_DB_PROVIDERS.keys())[provider_idx - 1]
        url = _DB_PROVIDERS[provider]
        console.print(f"已选择 {provider}，正在打开 {url}（请创建项目后获取连接串）")
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001 - 非交互环境打不开浏览器不致命
            console.print(f"（浏览器未自动打开，请手动访问：{url}）")
        console.print("在控制台找到 Connection string（形如 postgresql://...），复制后粘贴到下方")
    else:
        provider = None
        console.print("手动输入 DATABASE_URL")

    # 2. 输入 DATABASE_URL（敏感，getpass 预填当前值）
    var = next(v for v in schema_group["variables"] if v["name"] == "DATABASE_URL")
    prompt = _format_prompt(var, current)
    while True:
        value = console.getpass(prompt + " 留空取消", default=current)
        value = (value or "").strip()
        if not value:
            # 空输入 → 确认是否取消
            if console.confirm("未输入 DATABASE_URL，确认放弃本次采集？", default=True):
                console.print("已取消，未写入（回到分组菜单）")
                return False
            continue  # 重新输入
        return _write_database(state, schema_group, group_id, profile, console, value)


def _write_database(state: Dict[str, Any], schema_group: Dict[str, Any],
                    group_id: str, profile: str, console: Console, value: str) -> bool:
    """写入 database 分组单个 DATABASE_URL 值。"""
    existing = _existing_group(state, group_id, profile)
    var = next(v for v in schema_group["variables"] if v["name"] == "DATABASE_URL")
    current = _current_value(var, existing, profile)
    if value == current and current:
        prev_source = existing.get("DATABASE_URL", {}).get("source")
        source = prev_source or ("default" if value == _schema_default(var, profile) else "prompt")
    elif value == _schema_default(var, profile):
        source = "default"
    else:
        source = "prompt"
    new_group = {
        "DATABASE_URL": {
            "value": value,
            "source": source,
            "required": bool(var.get("required")),
            "description": var.get("description", ""),
            "sensitive": True,
        }
    }
    state["profiles"][profile]["env_groups"][group_id] = new_group
    return True


def _collect_payment(state: Dict[str, Any], schema_group: Dict[str, Any],
                     group_id: str, profile: str, console: Console, hint: str) -> None:
    """payment 分组采集：选 Stripe / Creem → 打开对应控制台 → 打印创建步骤
    → 仅采集所选提供商变量 → VITE_PAYMENT_PROVIDER 自动写入。

    选「跳过/手动输入」则走完整 _collect_profile（采集全部 16 变量，给手动用户兜底）。
    """
    console.print(f"采集 {group_id}/{profile}（{schema_group.get('description', group_id)}，{hint}）")
    names = list(_PAYMENT_PROVIDERS.keys())
    provider_idx = console.choose("选择支付提供商", names + ["跳过/手动输入"],
                                  default=len(names) + 1)
    if provider_idx > len(names):
        console.print("手动采集全部 payment 变量")
        _collect_profile(state, schema_group, group_id, profile, console, hint)
        return

    provider = names[provider_idx - 1]
    info = _PAYMENT_PROVIDERS[provider]
    url = info["url"]
    console.print(f"已选择 {provider}，正在打开 {url}")
    open_success = False
    try:
        webbrowser.open(url)
        open_success = True
    except Exception:  # noqa: BLE001 - 非交互环境打不开浏览器不致命
        console.print(f"（浏览器未自动打开，请手动访问：{url}）")

    base_url = _profile_base_url(state, profile)
    if not base_url:
        console.print("提示：尚未采集 NEXT_PUBLIC_BASE_URL（core 分组），创建 Webhook 时按 <base_url> 自行替换实际域名")
    if open_success:
        console.print("\n创建步骤：")
        for i, step in enumerate(info["guide"](base_url), start=1):
            console.print(f"  {i}: {step}")

    # 仅采集所选提供商变量 + 自动写入 VITE_PAYMENT_PROVIDER
    existing = _existing_group(state, group_id, profile)
    var_by_name = {v["name"]: v for v in schema_group["variables"]}
    wanted = list(info["vars"]) + ["VITE_PAYMENT_PROVIDER"]
    new_group: Dict[str, Any] = {}
    for name in wanted:
        var = var_by_name.get(name)
        if var is None:
            continue
        if name == "VITE_PAYMENT_PROVIDER":
            value = info["provider_value"]
            source = "prompt"
        else:
            current = _current_value(var, existing, profile)
            value = _collect_one(console, var, current)
            if not value and var.get("generate_if_empty"):
                if console.confirm(f"  {name} 是否自动生成？", default=True):
                    value = gen_better_auth_secret()
                    source = "prompt_or_generate"
                else:
                    source = "default"
            elif not value:
                source = "default" if _schema_default(var, profile) else "prompt"
            elif value == current and current:
                prev_source = existing.get(name, {}).get("source")
                if prev_source:
                    source = prev_source
                elif value == _schema_default(var, profile):
                    source = "default"
                else:
                    source = "prompt"
            else:
                source = "prompt"
        field = {
            "value": value,
            "source": source,
            "required": bool(var.get("required")),
            "description": var.get("description", ""),
        }
        if var.get("sensitive"):
            field["sensitive"] = True
        if var.get("generate_if_empty"):
            field["generate_if_empty"] = True
        new_group[name] = field

    state["profiles"][profile]["env_groups"][group_id] = new_group
