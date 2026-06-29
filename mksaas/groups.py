"""mksaas.groups — 分组标识符连字符↔下划线映射与固定顺序。

REQUIREMENTS §5.2：group key 用下划线，CLI 命令用连字符，二者一一映射；
CLI 与 apply 遍历顺序固定为 01~18 文档序号。
"""

from __future__ import annotations

from typing import List

# 固定顺序（与 docs/env-groups/01~18 一致），同时也是映射基准。
_GROUP_ORDER: List[str] = [
    "core",
    "database",
    "better_auth",
    "github_oauth",
    "google_oauth",
    "email",
    "newsletter",
    "storage",
    "payment",
    "configurations",
    "analytics",
    "notification",
    "affiliate",
    "captcha",
    "crisp",
    "cron_jobs",
    "ai",
    "firecrawl",
]

# 下划线 -> 连字符
_TO_KEBAB = {g: g.replace("_", "-") for g in _GROUP_ORDER}
# 连字符 -> 下划线
_TO_SNAKE = {v: k for k, v in _TO_KEBAB.items()}


def groups_in_order() -> List[str]:
    """返回固定顺序的 group id（下划线形式）列表。"""
    return list(_GROUP_ORDER)


def group_snake_to_kebab(group_id: str) -> str:
    """下划线形式转连字符形式，未知抛 KeyError。"""
    if group_id not in _TO_KEBAB:
        raise KeyError(group_id)
    return _TO_KEBAB[group_id]


def group_kebab_to_snake(group_id: str) -> str:
    """连字符形式转下划线形式，未知抛 KeyError。"""
    if group_id not in _TO_SNAKE:
        raise KeyError(group_id)
    return _TO_SNAKE[group_id]


# 分组中文摘要（供 init 概要展示与 env help 复用，单一来源）。
GROUP_SUMMARIES = {
    "core": "基础站点 URL 与回调地址",
    "database": "数据库连接",
    "better_auth": "认证密钥与鉴权核心配置",
    "github_oauth": "GitHub 登录配置",
    "google_oauth": "Google 登录配置",
    "email": "事务邮件配置（Resend）",
    "newsletter": "订阅与 Newsletter 配置（Beehiiv）",
    "storage": "对象存储配置",
    "payment": "支付配置",
    "configurations": "通用业务开关与运行配置",
    "analytics": "统计分析配置",
    "notification": "通知渠道配置",
    "affiliate": "联盟分销配置",
    "captcha": "人机验证配置",
    "crisp": "Crisp 在线客服配置",
    "cron_jobs": "定时任务鉴权配置",
    "ai": "AI 模型与密钥配置",
    "firecrawl": "Firecrawl 抓取配置",
}


def group_summary(group_id: str) -> str:
    """返回分组的中文摘要，未知抛 KeyError。"""
    if group_id not in GROUP_SUMMARIES:
        raise KeyError(group_id)
    return GROUP_SUMMARIES[group_id]


def is_required_group(group_id: str) -> bool:
    """该分组是否含必填变量（core/database/better_auth 等必填组）。

    通过 schema 判定：组内任一 variable.required 为真即为必填组。
    """
    from mksaas.schema import find_group  # 延迟导入避免循环
    group = find_group(group_id)
    return any(bool(v.get("required")) for v in group.get("variables", []))
