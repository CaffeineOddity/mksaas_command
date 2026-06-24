"""mksaas.commands.init — 全流程编排器。

docs/steps/01-init.md 为真相来源。按 project → env×N → apply 顺序引导，
每步先确认、可跳过，apply 前停一次确认。支持续跑。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mksaas import groups, state
from mksaas.console import Console


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_project_step(console: Console) -> int:
    """执行 project 子步骤（薄包装，便于编排测试桩）。"""
    from mksaas.commands.project import run_project
    return run_project(_ns("project"), console)


def _run_env_step(group_id: str, console: Console) -> int:
    """执行 env 子步骤。"""
    from mksaas.commands.env import run_env
    return run_env(_ns("env", group=groups.group_snake_to_kebab(group_id), profile="test"), console)


def _run_apply_step(console: Console) -> int:
    """执行 apply 子步骤。"""
    from mksaas.commands.apply import run_apply
    return run_apply(_ns("apply"), console)


def _ns(command: str, **kw) -> Any:
    """构造子命令 Namespace。"""
    base = {"command": command, "version": False}
    base.update(kw)
    import argparse
    return argparse.Namespace(**base)


def run_init(args: Any, console: Console) -> int:
    """init 子命令入口：编排 project → env×N → apply。"""
    sp = state.locate_state_file(_cwd())
    if sp is None:
        # 无状态文件 → 必须先跑 project（project 负责创建状态）
        console.print("未找到状态文件，开始执行 project 步骤（project 为必填，不可跳过）")
        rc = _run_project_step(console)
        if rc != 0:
            console.print("project 步骤未完成，已终止编排")
            return rc
        sp = state.locate_state_file(_cwd())
        if sp is None:
            console.print("project 未就位状态文件，已终止")
            return 1

    data = state.load(sp)
    init_step = data.setdefault("steps", {}).setdefault("init", {})
    processed = set(init_step.get("env_groups_processed", []))
    skipped = set(init_step.get("env_groups_skipped", []))

    # project 必填：若尚未完成，提示并执行
    if data.get("steps", {}).get("project", {}).get("status") != "completed":
        console.print("project 尚未完成。project 为必填步骤，是否现在执行？")
        if not console.confirm("执行 project？", default=True):
            console.print("project 为必填，已终止编排")
            return 1
        rc = _run_project_step(console)
        if rc != 0:
            return rc
        data = state.load(sp)

    # 逐个 env 分组
    for gid in groups.groups_in_order():
        if gid in processed or gid in skipped:
            continue
        console.print(f"分组 {groups.group_snake_to_kebab(gid)}：处理 / 跳过")
        if console.confirm(f"处理 {gid}？", default=False):
            _run_env_step(gid, console)
            processed.add(gid)
            init_step["env_groups_processed"] = sorted(processed)
        else:
            skipped.add(gid)
            init_step["env_groups_skipped"] = sorted(skipped)
        init_step["updated_at"] = _now()
        state.save(sp, data)

    # apply 前摘要 + 确认
    console.print("即将进入 apply 阶段。apply 摘要：")
    _summarize(console, data)
    init_step["apply_confirmed"] = console.confirm("是否立即执行 apply？", default=False)
    state.save(sp, data)
    if not init_step["apply_confirmed"]:
        console.print("可稍后单独执行 mksaas apply")
        return 0

    rc = _run_apply_step(console)
    data = state.load(sp)
    data["steps"]["init"]["applied"] = (rc == 0)
    data["steps"]["init"]["applied_at"] = _now() if rc == 0 else None
    state.save(sp, data)
    return rc


def _summarize(console: Console, data: dict) -> None:
    """apply 前摘要（敏感字段不打印完整值）。"""
    from mksaas.masking import mask
    for profile in ("test", "prod"):
        groups_map = data.get("profiles", {}).get(profile, {}).get("env_groups", {})
        console.print(f"[{profile}] 已采集：{', '.join(groups_map.keys()) or '(无)'}")
    console.print("（详细值在 apply 执行前由 apply 摘要展示，敏感字段脱敏）")


def _cwd():
    from pathlib import Path
    return Path.cwd()
