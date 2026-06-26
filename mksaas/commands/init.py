"""mksaas.commands.init — 全流程编排器。

docs/steps/01-init.md 为真相来源。按 project → env×N → apply 顺序引导。
每次 init 都从头走一遍 project → 全部 env 分组 → apply：对已有信息先展示，
再让用户选「修改 / 下一步 / 结束」。不再按 processed/skipped 静默跳过。
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


def _run_env_step(group_id: str, profile: str, console: Console) -> int:
    """执行 env 子步骤（采集指定 profile）。"""
    from mksaas.commands.env import run_env
    return run_env(_ns("env", group=groups.group_snake_to_kebab(group_id), profile=profile), console)


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
    """init 子命令入口：编排 project → env×N → apply。

    每次 init 都从头走一遍：对 project 与每个 env 分组先展示已有信息，
    再让用户选「修改/下一步/结束」（未采集的 env 分组为「处理/跳过/结束」）。
    """
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
    init_step["ended_early"] = False
    state.save(sp, data)

    # ── project：展示已有信息，选 修改/下一步/结束 ──
    project_rc = _project_step(console, sp)
    if project_rc is None:
        # project 步骤内已自行结束（选「结束」→ 询问 apply 后退出）
        return 0
    if not project_rc:
        return 1
    data = state.load(sp)

    # ── 逐个 env 分组：全部重走，不再按 processed/skipped 跳过 ──
    for gid in groups.groups_in_order():
        kebab = groups.group_snake_to_kebab(gid)
        _print_group_overview(console, data, gid)
        collected_test = _group_collected(data, gid, "test")
        collected_prod = _group_collected(data, gid, "prod")

        # 菜单随采集状态动态生成：已采集的 profile 给「修改」，未采集的给「采集」
        options = []
        if collected_test:
            options.append("修改 test")
        else:
            options.append("采集 test")
        if collected_prod:
            options.append("修改 prod")
        else:
            options.append("采集 prod")
        options.append("下一步")
        options.append("结束")

        choice = console.choose("", options, default=len(options) - 1)  # 默认「下一步」
        # 前两项是 test/prod 动作，后两项是 下一步/结束
        if choice <= 2:
            profile = "test" if choice == 1 else "prod"
            _run_env_step(gid, profile, console)
            data = state.load(sp)
            data["steps"]["init"]["updated_at"] = _now()
            state.save(sp, data)
            # 采集后继续停留在该分组（重新展示并出菜单），让用户接着改另一个 profile
            continue
        elif choice == len(options) - 1:  # 下一步
            data["steps"]["init"]["updated_at"] = _now()
            state.save(sp, data)
            continue
        else:  # 结束
            data["steps"]["init"]["ended_early"] = True
            data["steps"]["init"]["updated_at"] = _now()
            state.save(sp, data)
            return _ask_apply_after_end(console, data, data["steps"]["init"], sp)

    # ── 走完全部分组：apply 前摘要 + 确认 ──
    console.header("apply 摘要")
    _summarize(console, data)
    init_step["apply_confirmed"] = (console.choose("", ["执行", "暂不"], default=1) == 1)
    state.save(sp, data)
    if not init_step["apply_confirmed"]:
        console.print("可稍后单独执行 mksaas apply")
        return 0

    return _run_apply_and_record(console, sp, init_step)


def _project_step(console: Console, sp):
    """project 编排：展示已有信息，选 修改/下一步/结束。

    project 为必填：要么已采集（可下一步），要么修改/首次采集。
    返回 True=继续 env；False=终止（project 失败）；None=已在内部结束并退出。
    """
    data = state.load(sp)
    proj = data.get("project", {})
    if proj.get("repo_url"):
        console.header("project")
        console.print(f"  仓库地址：{proj['repo_url']}")
        console.print(f"  项目目录：{proj.get('project_dir')}")
        console.print(f"  应用策略：{proj.get('apply_strategy')}  should_push={proj.get('should_push')}")
        choice = console.choose("", ["修改 repo url", "下一步", "结束"], default=2)
        if choice == 1:  # 修改 repo url：直接输入新地址，不走 clone/来源采集
            new_url = _edit_repo_url(console, proj["repo_url"])
            if new_url is not None:
                data = state.load(sp)
                data["project"]["repo_url"] = new_url
                data.setdefault("steps", {}).setdefault("init", {})["updated_at"] = _now()
                state.save(sp, data)
                console.print(f"仓库地址已更新：{new_url}")
        elif choice == 3:  # 结束
            fresh = state.load(sp)
            fresh.setdefault("steps", {}).setdefault("init", {})["ended_early"] = True
            fresh["steps"]["init"]["updated_at"] = _now()
            state.save(sp, fresh)
            _ask_apply_after_end(console, fresh, fresh["steps"]["init"], sp)
            return None  # 已在内部结束并退出
        # choice == 2 下一步：继续 env
    else:
        # 尚未采集 project：必填，直接执行
        console.print("project 尚未采集（project 为必填，不可跳过），开始执行")
        rc = _run_project_step(console)
        if rc != 0:
            console.print("project 未完成，已终止编排")
            return False
        fresh = state.load(sp)
        fresh.setdefault("steps", {}).setdefault("init", {})["updated_at"] = _now()
        state.save(sp, fresh)
    return True


def _edit_repo_url(console: Console, current: str):
    """直接编辑 repo url：预填当前值，留空=取消返回 None。"""
    from mksaas.repo_url import clean_repo_url
    raw = console.input("  repo url（留空取消）", default=current)
    raw = (raw or "").strip()
    if not raw or raw == current:
        return None
    try:
        cleaned, stripped = clean_repo_url(raw)
    except ValueError as exc:
        console.print(str(exc))
        return None
    if stripped:
        console.print("检测到地址含鉴权段，已剥离；请改用 SSH key 或 HTTPS 凭据转发")
    return cleaned


def _run_apply_and_record(console: Console, sp, init_step: dict) -> int:
    """执行 apply 并回写 init.applied。"""
    rc = _run_apply_step(console)
    data = state.load(sp)
    data["steps"]["init"]["applied"] = (rc == 0)
    data["steps"]["init"]["applied_at"] = _now() if rc == 0 else None
    state.save(sp, data)
    return rc


def _ask_apply_after_end(console: Console, data: dict, init_step: dict, sp) -> int:
    """用户中途选择「结束」后：询问是否立即 apply。"""
    console.header("apply 摘要")
    _summarize(console, data)
    do_apply = console.choose("", ["执行", "暂不"], default=2) == 1
    init_step["apply_confirmed"] = do_apply
    state.save(sp, data)
    if not do_apply:
        console.print("可稍后单独执行 mksaas apply")
        return 0
    return _run_apply_and_record(console, sp, init_step)


def _group_collected(data: dict, gid: str, profile: str) -> bool:
    """该分组在指定 profile 是否已采集。"""
    return gid in data.get("profiles", {}).get(profile, {}).get("env_groups", {})


def _print_group_overview(console: Console, data: dict, gid: str) -> None:
    """进入分组前展示概要：摘要、变量数/必填数、各 profile 采集状态与现有值（脱敏）。"""
    from mksaas.masking import mask
    from mksaas.schema import find_group
    kebab = groups.group_snake_to_kebab(gid)
    summary = groups.group_summary(gid)
    schema = find_group(gid)
    variables = schema.get("variables", [])
    total = len(variables)
    required_n = sum(1 for v in variables if v.get("required"))
    sensitive_names = {v["name"] for v in variables if v.get("sensitive")}
    console.header(f"分组 {kebab}（{summary}）")
    console.print(f"变量：{total} 个（必填 {required_n}）")
    for profile in ("test", "prod"):
        fields = data.get("profiles", {}).get(profile, {}).get("env_groups", {}).get(gid, {})
        if not fields:
            console.print(f"  {profile}=未采集")
            continue
        parts = []
        for name, field in fields.items():
            raw = field.get("value", "")
            shown = mask(raw) if name in sensitive_names else (raw or "<empty>")
            parts.append(f"{name}={shown}")
        console.print(f"  {profile}=已采集  {'; '.join(parts)}")


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
