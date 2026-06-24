"""mksaas.groups — 分组标识符连字符↔下划线映射与固定顺序。

REQUIREMENTS §5.2：group key 用下划线，CLI 命令用连字符，二者一一映射；
CLI 与 apply 遍历顺序固定为 01~17 文档序号。
"""

from __future__ import annotations

from typing import List

# 固定顺序（与 docs/env-groups/01~17 一致），同时也是映射基准。
_GROUP_ORDER: List[str] = [
    "core",
    "database",
    "better_auth",
    "github_oauth",
    "google_oauth",
    "email_newsletter",
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
