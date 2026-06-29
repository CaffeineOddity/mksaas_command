"""mksaas.commands.apply — 统一执行落地。

docs/steps/04-apply.md 为真相来源。
执行前 check（project/目录一致性/git remote/必填项）→ 重建+同步 → 一律尝试 push
（失败不阻断，按 stderr 分类提示）→ 生成 SETUP_NEXT_STEPS.md → 回写 steps.apply。
不读 should_push/apply_strategy（二者已不在状态文件中）。
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


def _summarize(console: Console, data: dict, profile: str) -> None:
    """汇总将被应用的配置与 push 计划（敏感字段 mask）。"""
    proj = data.get("project", {})
    console.header("apply 摘要")
    for p in ("test", "prod"):
        groups = data.get("profiles", {}).get(p, {}).get("env_groups", {})
        console.print(f"[{p}] 已采集分组：{', '.join(groups.keys()) or '(无)'}")
        for gid, fields in groups.items():
            for name, field in fields.items():
                val = field.get("value", "")
                shown = mask(val) if field.get("sensitive") else (val or "<empty>")
                console.print(f"  {p}/{gid}/{name} = {shown}")
    console.print(f"目标 profile：{profile}（根 .env 将同步自 {profile}）")
    console.print(f"push 计划：将尝试 push 到 {proj.get('repo_url') or '(空)'}")


def _check(args: Any, console: Console, cwd: Path) -> tuple[Path, dict, Path] | int:
    """执行前 check（§3）。通过返回 (project_dir, data, sp)；不通过返回 rc(int)。"""
    sp = state.locate_state_file(cwd)
    if sp is None:
        console.print("未找到 .mksaas/setup-state.json，请先执行 mksaas project")
        return 1

    data = state.load(sp)
    proj = data.get("project", {})
    project_dir_str = proj.get("project_dir")
    repo_url = proj.get("repo_url")
    if not project_dir_str or not repo_url:
        console.print("缺少 project 信息，请先执行 mksaas project 完成项目就位")
        return 1

    project_dir = Path(project_dir_str)
    # 当前目录须与 project_dir 一致
    if cwd.resolve() != project_dir.resolve():
        console.print(f"当前目录与项目目录不一致：当前={cwd} 项目={project_dir}")
        console.print(f"请执行 cd {project_dir} 后重试 mksaas apply")
        return 1
    # 当前目录须是 git 仓库且 remote 含 repo_url（同一仓库判据）
    if not gitops.is_git_repo(project_dir):
        console.print(f"项目目录不是 git 仓库：{project_dir}")
        return 1
    if not gitops.has_remote(project_dir, repo_url):
        console.print(f"项目目录的 remote 不含 {repo_url}，疑似非同一仓库")
        console.print("请回到 mksaas project 处理项目就位")
        return 1

    return project_dir, data, sp


def run_apply(args: Any, console: Console) -> int:
    """apply 子命令入口。"""
    cwd = _cwd()
    checked = _check(args, console, cwd)
    if isinstance(checked, int):
        return checked
    project_dir, data, sp = checked

    schema = load_schema()

    # 目标 profile：--profile 指定，缺省 test。仅校验该 profile 必填项。
    profile = getattr(args, "profile", None) or "test"

    # 全量重建两文件（反映当前采集状态）；必填校验只针对目标 profile
    missing = env_writer.rebuild_envs(data, schema, project_dir)
    profile_missing = missing.get(profile, [])
    if profile_missing:
        console.print(f"[{profile}] 环境必填项缺失：{', '.join(sorted(set(profile_missing)))}")
        console.print(f"请返回 mksaas env <group> --profile {profile} 补全后再执行 apply")
        _cleanup_partial(project_dir)
        state.save(sp, data)
        return 1

    _summarize(console, data, profile)

    if not console.confirm("是否立即执行 apply？", default=False):
        console.print("已取消，可稍后单独执行 mksaas apply")
        state.save(sp, data)
        return 0

    # 同步根 .env：来自目标 profile
    env_writer.sync_root_env(data, project_dir, profile)

    # 一律尝试 push（不读 should_push）；失败不阻断
    push_result = _try_push(console, project_dir)

    # 生成 SETUP_NEXT_STEPS.md
    _write_next_steps(project_dir, data, profile, push_result)

    # 回写
    data = state.load(sp)
    data["steps"]["apply"] = {
        "status": "completed", "updated_at": _now(),
        "applied": True, "applied_at": _now(),
    }
    data["apply"] = {
        "dirty": False, "last_run_at": _now(),
        "last_result": "pushed" if push_result == "success" else "push_failed",
        "last_applied_project_dir": str(project_dir),
        "push_result": push_result,
        "last_profile": profile,
    }
    state.save(sp, data)
    console.print("apply 完成")
    return 0


def _try_push(console: Console, project_dir: Path) -> str:
    """一律尝试 push，按 stderr 分类提示；返回 push_result。"""
    ok, err = gitops.push(project_dir)
    if ok:
        console.print("push 成功")
        return "success"
    err_text = (err or "").strip()
    low = err_text.lower()
    if "non-fast-forward" in low or "rejected" in low or "fetch first" in low:
        console.print("push 失败：远程已有内容（non-fast-forward）")
        console.print("请手动执行 git pull --rebase 后重新 mksaas apply")
    elif "denied" in low or "permission" in low or "authentication" in low:
        console.print("push 失败：鉴权未通过")
        console.print("请检查本地凭据（SSH key / gh auth login / credential helper）")
    else:
        console.print("push 失败")
        console.print(f"详情：{err_text[:200]}")
    return "failed"


def _cleanup_partial(project_dir: Path) -> None:
    """必填缺失时清理刚生成的残缺 env 文件。"""
    for name in (".env.test", ".env.prod"):
        p = project_dir / ".mksaas" / name
        if p.exists():
            p.unlink()


def _write_next_steps(project_dir: Path, data: dict, profile: str,
                      push_result: str) -> None:
    """生成 SETUP_NEXT_STEPS.md。"""
    p = project_dir / "SETUP_NEXT_STEPS.md"
    lines = [
        "# 后续步骤",
        "",
        "- 环境文件已生成：.mksaas/.env.test、.mksaas/.env.prod",
        f"- 根 .env 已同步自 {profile}",
        "- 运行 `pnpm install` 安装依赖",
        "- 运行 `pnpm run dev` 验证环境是否正确",
    ]
    if push_result != "success":
        lines.append("- push 未成功：请按终端提示处理后重新执行 `mksaas apply`")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _cwd():
    from pathlib import Path
    return Path.cwd()
