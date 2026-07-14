"""mksaas.commands.project — 项目信息采集与本地就位。

docs/steps/02-project.md 为真相来源。本命令：
- 初始化/读取 .mksaas/setup-state.json
- 询问用户仓库情况（已有仓库地址 / 没有仓库，新建仓库），采集 repo_url
- clone 用户仓 → 检测空/非空 → 分流（已存关联模版仓库 / 空仓库用模板初始化）
- 不执行 push（push 在 apply），不记录 apply 策略标记
- 结尾提示 cd 到 project_dir 后执行 mksaas env
"""

from __future__ import annotations

import shutil
import webbrowser
from pathlib import Path
from typing import Any

from mksaas import gitops, state
from mksaas.console import Console
from mksaas.repo_url import clean_repo_url


def _open_browser(url: str) -> None:
    """打开浏览器（薄函数，便于测试桩）。"""
    webbrowser.open(url)


def _derive_project_dir_name(repo_url: str) -> str:
    """从 repo_url 推导默认本地目录名（亦作 repo_name）。"""
    clean = repo_url.rstrip("/")
    if clean.endswith(".git"):
        clean = clean[:-4]
    name = clean.rsplit("/", 1)[-1]
    return name or "project"


def _write_project(state_path: Path, project: dict) -> None:
    """回写 project 块到状态文件。"""
    if not state_path.is_file():
        state.save(state_path, state.init_default())
    data = state.load(state_path)
    data["project"].update(project)
    data.setdefault("steps", {}).setdefault("project", {})
    data["steps"]["project"]["status"] = "completed"
    state.save(state_path, data)


def _place_and_finalize(console: Console, project_dir: Path,
                        repo_url: str, extra: dict) -> int:
    """就位后建 .mksaas、回写状态、提示 cd。

    extra 仅含 repo_url/repo_name/project_dir 之外的补充字段（如 template_*），
    不含任何 apply 策略标记。
    """
    state.ensure_state_dir(project_dir)
    sp = project_dir / state.STATE_DIRNAME / state.STATE_FILENAME
    project = {
        "repo_url": repo_url,
        "repo_name": _derive_project_dir_name(repo_url),
        "project_dir": str(project_dir),
    }
    project.update(extra)
    _write_project(sp, project)
    console.print(f"项目就位：{project_dir}")
    console.print(f"请执行 cd {project_dir} 后运行 mksaas env <group> 补全环境配置")
    return 0


def run_project(args: Any, console: Console) -> int:
    """project 子命令入口（§4.2 判定流）。"""
    cwd = Path.cwd()

    # 1. 当前目录已有状态文件 → 展示已有 project，确认是否修改
    sp = state.locate_state_file(cwd)
    if sp is not None:
        data = state.load(sp)
        proj = data.get("project", {})
        if proj.get("repo_url"):
            console.print(f"已有仓库地址：{proj['repo_url']}")
            console.print(f"已有项目目录：{proj.get('project_dir')}")
            if not console.confirm("是否修改已有项目配置？", default=False):
                console.print(
                    f"请执行 cd {proj.get('project_dir', cwd)} 后运行 mksaas env <group>")
                return 0
            # 用户要修改：重新走判定流（§4.2 第 2/3 步），不预填 repo_url
            if gitops.is_git_repo(cwd):
                url = gitops.remote_url(cwd, "origin")
                if not url:
                    remotes = gitops.remotes(cwd)
                    url = next(iter(remotes.values()), None) if remotes else None
                if url:
                    repo_url, _ = clean_repo_url(url)
                    return _dispatch_by_content(console, cwd, repo_url, already_placed=True)
            return _collect_repo_url_and_place(console, cwd, sp)

    # 2. 当前目录是 git 仓库 → project_dir=cwd，从 remote 推断 repo_url，不 clone
    if gitops.is_git_repo(cwd):
        url = gitops.remote_url(cwd, "origin")
        if not url:
            # origin 缺失：取任一 remote
            remotes = gitops.remotes(cwd)
            url = next(iter(remotes.values()), None) if remotes else None
        if not url:
            console.print("当前目录是 git 仓库但无 remote，请先配置 remote 或换目录")
            return 1
        repo_url, _ = clean_repo_url(url)
        # §7.5：直接进入内容分流（不 clone）
        return _dispatch_by_content(console, cwd, repo_url, already_placed=True)

    # 3. 全新：询问用户仓库情况
    return _collect_repo_url_and_place(console, cwd, None)


def _collect_repo_url_and_place(console: Console, cwd: Path,
                                sp: Path | None) -> int:
    """§7.1：询问用户仓库情况（二选一），采集 repo_url 后就位。"""
    choice = console.choose(
        "请选择仓库情况",
        ["已有仓库地址", "没有仓库，新建仓库"],
        default=1,
    )

    if choice == 1:
        console.print("请输入已有仓库地址（git@... 或 https://...）")
        raw_url = console.input("repo_url> ").strip()
    else:
        # 没有仓库：打开 github.com/new，等用户创建空私仓后回填
        console.print("将在浏览器打开 https://github.com/new，请创建空私仓")
        _open_browser("https://github.com/new")
        console.print("创建完成后，请输入新建仓库的地址：")
        raw_url = console.input("repo_url> ").strip()

    if not raw_url:
        console.print("未输入仓库地址，已取消")
        return 1

    try:
        repo_url, stripped = clean_repo_url(raw_url)
    except ValueError as exc:
        console.print(str(exc))
        return 1
    if stripped:
        console.print("检测到地址含鉴权段，已剥离；请改用 SSH key 或 HTTPS 凭据转发")

    project_dir = cwd / _derive_project_dir_name(repo_url)
    return _clone_or_reuse_and_dispatch(console, project_dir, repo_url)


def _clone_or_reuse_and_dispatch(console: Console, project_dir: Path,
                                 repo_url: str) -> int:
    """§7.2：三分判定（同仓复用 / 另一个仓库 / 非 git 目录）+ clone，再分流。"""
    if project_dir.exists():
        if gitops.is_git_repo(project_dir):
            if gitops.has_remote(project_dir, repo_url):
                # 同一仓库：复用，不重新 clone
                return _dispatch_by_content(console, project_dir, repo_url,
                                            already_placed=True)
            console.print(f"目录已存在且是另一个仓库：{project_dir}")
            console.print("不覆盖；请改名或换目录后重试")
            return 1
        console.print(f"目录已存在且非 git 仓库：{project_dir}")
        console.print("不覆盖；请清理后重试或换目录")
        return 1

    if not console.confirm(f"将 clone {repo_url} 到 {project_dir}？", default=True):
        console.print("已取消")
        return 1
    if not gitops.clone(repo_url, project_dir):
        console.print("clone 失败：请检查 SSH key / gh auth login / credential helper")
        return 1
    return _dispatch_by_content(console, project_dir, repo_url, already_placed=False)


def _dispatch_by_content(console: Console, project_dir: Path,
                         repo_url: str, already_placed: bool) -> int:
    """§4.2 第 5 步：按仓库内容分流。

    - 有内容（has_commits）→ §7.3 已存关联模版仓库：建/复用状态，不写 template_*
    - 空仓库 → §7.4：rmtree 刚 clone 的空仓，用模板 clone 出 project_dir + add origin
    """
    if gitops.has_commits(project_dir):
        # §7.3 已存关联模版仓库
        return _place_and_finalize(console, project_dir, repo_url, extra={})

    # §7.4 空仓库：删掉刚 clone 的用户空仓，改用模板初始化
    if not already_placed:
        shutil.rmtree(project_dir, ignore_errors=True)

    DEFAULT_TEMPLATE_REPO = "https://github.com/MkSaaSHQ/mksaas-template.git"
    DEFAULT_TEMPLATE_BRANCH = "main"

    console.print("[检测到空仓库，将用模板初始化项目目录]")
    template_repo = console.input(
        "template_repo> ", default=DEFAULT_TEMPLATE_REPO,
    ).strip()
    template_branch = console.input(
        "template_branch> ", default=DEFAULT_TEMPLATE_BRANCH,
    ).strip()

    if not console.confirm(
            f"将从 {template_repo} 初始化到 {project_dir}？", default=True):
        console.print("已取消")
        return 1
    if not gitops.clone(template_repo, project_dir, origin="upstream"):
        console.print("模板 clone 失败：请检查 SSH key / gh auth login / credential helper")
        return 1
    gitops.checkout_set_upstream(project_dir, template_branch)
    gitops.remote_add(project_dir, "origin", repo_url)
    return _place_and_finalize(console, project_dir, repo_url, extra={
        "template_repo": template_repo,
        "template_branch": template_branch,
    })
