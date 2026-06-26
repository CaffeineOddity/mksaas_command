"""mksaas.prompts — 通用环境分组采集交互。

docs/env-groups/*.md §5 为采集流程模板；REQUIREMENTS §3.3 为交互确认顺序。
依赖 Console 缝与 schema。collect_group：一次性采集 test 与 prod 两个 profile，
每行变量预填当前值/schema 默认值，留空=保留。敏感字段走 getpass。
"""

from __future__ import annotations

import re
from typing import Any, Dict

from mksaas.console import Console
from mksaas.masking import mask
from mksaas.schema import find_group
from mksaas.secrets_gen import gen_better_auth_secret

# 视为 URL 的变量名（采集时校验 http/https）
_URL_VARS = {"NEXT_PUBLIC_BASE_URL"}

_URL_RE = re.compile(r"^https?://[^\s]+$")


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
    """
    schema_group = find_group(group_id)
    summary = schema_group.get("description") or group_id
    hint = "测试环境，可用 localhost/占位值" if profile == "test" else "正式环境，请填写真实域名/密钥"

    console.print(f"采集 {group_id}/{profile}（{summary}，{hint}）：每行留空=保留，输入新值=覆盖")
    _collect_profile(state, schema_group, group_id, profile, console, hint)
    console.print(f"分组 {group_id}/{profile} 已采集（未应用，需在 apply 阶段统一落地）")
    return True
