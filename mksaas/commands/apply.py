"""mksaas.commands.apply — 统一执行落地。

docs/steps/02-apply.md 为真相来源。
project 缺失→终止；必填缺失→提示补全；确认→env_writer 重建+同步；
should_push 决定是否 push；生成 SETUP_NEXT_STEPS.md；回写 steps.apply。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mksaas import env_writer, gitops, state
from mksaas.console import Console
from mksaas.masking import mask
from mksaas.schema import load_schema


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _summarize(console: Console, data: dict) -> None:
    """汇总将被应用的配置与 push 计划（敏感字段 mask）。"""
    proj = data.get("project", {})
    console.print("==== apply 摘要 ====")
    for profile in ("test", "prod"):
        groups = data.get("profiles", {}).get(profile, {}).get("env_groups", {})
        console.print(f"[{profile}] 已采集分组：{', '.join(groups.keys()) or '(无)'}")
        for gid, fields in groups.items():
            for name, field in fields.items():
                val = field.get("value", "")
                shown = mask(val) if field.get("sensitive") else (val or "<empty>")
                console.print(f"  {profile}/{gid}/{name} = {shown}")
    console.print(f"push 计划：should_push={proj.get('should_push')} repo_url={proj.get('repo_url') or '(空)'}")
    console.print("====================")


def run_apply(args: Any, console: Console) -> int:
    """apply 子命令入口。"""
    sp = state.locate_state_file(_cwd())
    if sp is None:
        console.print("未找到 .mksaas/setup-state.json，请先执行 mksaas project")
        return 1

    data = state.load(sp)
    proj = data.get("project", {})
    if not proj.get("project_dir") or "repo_url" not in proj:
        console.print("缺少 project 信息，请先执行 mksaas project 完成项目就位")
        return 1

    project_dir = Path(proj["project_dir"])
    schema = load_schema()

    # 校验环境必填项
    missing = env_writer.rebuild_envs(data, schema, project_dir)
    # rebuild 已回写 generate 值，但必填缺失时不写文件——这里先回滚文件判定
    all_missing = missing.get("test", []) + missing.get("prod", [])
    if all_missing:
        console.print(f"环境必填项缺失：{', '.join(sorted(set(all_missing)))}")
        console.print("请返回 mksaas env <group> 补全后再执行 apply")
        # 删除刚生成的（必填缺失时文件含残缺）→ 重新清理
        _cleanup_partial(project_dir)
        state.save(sp, data)
        return 1

    _summarize(console, data)

    if not console.confirm("是否立即执行 apply？", default=False):
        console.print("已取消，可稍后单独执行 mksaas apply")
        state.save(sp, data)
        return 0

    # 同步根 .env
    profile = _ask_sync_profile(console)
    env_writer.sync_root_env(data, project_dir, profile)

    # push
    should_push = bool(proj.get("should_push")) and bool(proj.get("repo_url"))
    push_ok = True
    if should_push:
        ok, err = gitops.push(project_dir)
        if not ok:
            console.print("push 失败：请检查本地凭据（SSH key / gh auth login / credential helper）")
            console.print(f"详情：{err.strip()[:200]}")
            push_ok = False

    # 生成 SETUP_NEXT_STEPS.md
    _write_next_steps(project_dir, data, profile, push_ok)

    # 回写
    data["steps"]["apply"] = {
        "status": "completed", "updated_at": _now(),
        "applied": True, "applied_at": _now(),
    }
    data["apply"] = {
        "dirty": False, "last_run_at": _now(),
        "last_result": "pushed" if should_push and push_ok else "applied_no_push",
        "last_applied_project_dir": str(project_dir),
    }
    state.save(sp, data)
    console.print("apply 完成")
    return 0


def _ask_sync_profile(console: Console) -> str:
    """询问 .env 同步 test 还是 prod。"""
    console.print(".env 同步来源：test / prod")
    raw = console.input("sync> ").strip().lower()
    return raw if raw in ("test", "prod") else "test"


def _cleanup_partial(project_dir: Path) -> None:
    """必填缺失时清理刚生成的残缺 env 文件。"""
    for name in (".env.test", ".env.prod"):
        p = project_dir / ".mksaas" / name
        if p.exists():
            p.unlink()


def _write_next_steps(project_dir: Path, data: dict, profile: str, push_ok: bool) -> None:
    """生成 SETUP_NEXT_STEPS.md。"""
    p = project_dir / "SETUP_NEXT_STEPS.md"
    lines = [
        "# 后续步骤",
        "",
        f"- 环境文件已生成：.mksaas/.env.test、.mksaas/.env.prod",
        f"- 根 .env 已同步自 {profile}",
        "- 运行 `pnpm install` 安装依赖",
        "- 运行 `pnpm run dev` 验证环境是否正确",
    ]
    if not push_ok:
        lines.append("- push 失败：请检查本地 git 凭据后重新执行 `mksaas apply`")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _cwd():
    from pathlib import Path
    return Path.cwd()
