"""mksaas.commands.env — 环境分组采集命令。

docs/env-groups/*.md §3/§4；REQUIREMENTS §5.1、§5.2。
逐步模式要求当前目录已是 project 就位过的项目目录。
"""

from __future__ import annotations

from typing import Any

from mksaas import groups, prompts, state
from mksaas.console import Console


def run_env(args: Any, console: Console) -> int:
    """env 子命令入口：采集某一环境分组写入指定 profile。"""
    sp = state.locate_state_file(_cwd())
    if sp is None:
        console.print("未找到 .mksaas/setup-state.json，请先执行 mksaas project 完成项目就位")
        return 1

    group_arg = getattr(args, "group", None)
    if not group_arg:
        _list_groups(console)
        console.print("请指定分组：mksaas env <group> [--profile test|prod]")
        return 1

    try:
        group_id = groups.group_kebab_to_snake(group_arg)
    except KeyError:
        console.print(f"未知分组：{group_arg}")
        _list_groups(console)
        return 1

    profile = getattr(args, "profile", None) or "test"
    if profile not in ("test", "prod"):
        console.print(f"未知 profile：{profile}（仅支持 test / prod）")
        return 1

    data = state.load(sp)
    prompts.collect_group(data, group_id, profile, console)
    state.save(sp, data)
    return 0


def _list_groups(console: Console) -> None:
    """列出可用分组（连字符形式）。"""
    console.print("可用分组：")
    for gid in groups.groups_in_order():
        console.print(f"  {groups.group_snake_to_kebab(gid)}")


def _cwd():
    """当前工作目录（薄函数，便于测试）。"""
    from pathlib import Path
    return Path.cwd()
