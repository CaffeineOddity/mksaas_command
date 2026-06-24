"""mksaas.commands.project — 项目信息采集与本地就位。

docs/steps/03-project.md 为真相来源。本命令：
- 初始化/读取 .mksaas/setup-state.json
- 采集 repo_url、仓库来源，让本地目录就位
- 不执行 push（push 在 apply）
- 结尾提示 cd 到 project_dir 后执行 mksaas env
"""

from __future__ import annotations

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
    """从 repo_url 推导默认本地目录名。"""
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
    """就位后建 .mksaas、回写状态、提示 cd。"""
    state.ensure_state_dir(project_dir)
    sp = project_dir / state.STATE_DIRNAME / state.STATE_FILENAME
    project = {
        "repo_url": repo_url,
        "project_dir": str(project_dir),
    }
    project.update(extra)
    _write_project(sp, project)
    console.print(f"项目就位：{project_dir}")
    console.print(f"请执行 cd {project_dir} 后运行 mksaas env <group> 补全环境配置")
    return 0


def run_project(args: Any, console: Console) -> int:
    """project 子命令入口。"""
    cwd = Path.cwd()

    # 1. 当前目录已有状态文件
    sp = state.locate_state_file(cwd)
    if sp is not None:
        data = state.load(sp)
        proj = data.get("project", {})
        if proj.get("repo_url"):
            console.print(f"已有仓库地址：{proj['repo_url']}")
            console.print(f"已有项目目录：{proj.get('project_dir')}")
            if not console.confirm("是否修改已有项目配置？", default=False):
                console.print(f"请执行 cd {proj.get('project_dir', cwd)} 后运行 mksaas env <group>")
                return 0
            # 用户要修改：落到下方采集流程，复用 cwd 作为 project_dir
            project_dir = Path(proj.get("project_dir", cwd))
            return _collect_and_place(console, cwd, project_dir, existing=data)

    # 2. 当前目录是 git 仓库
    if gitops.is_git_repo(cwd):
        url = gitops.remote_url(cwd, "origin")
        if url:
            url, _ = clean_repo_url(url)
            state.ensure_state_dir(cwd)
            sp = cwd / state.STATE_DIRNAME / state.STATE_FILENAME
            _write_project(sp, {
                "repo_url": url, "project_dir": str(cwd),
                "apply_strategy": "existing_local", "should_push": False,
            })
            console.print(f"检测到当前已是 git 仓库：{url}")
            console.print(f"请执行 cd {cwd} 后运行 mksaas env <group> 补全环境配置")
            return 0

    # 3. 全新：采集 repo_url 与来源
    return _collect_and_place(console, cwd, None, existing=None)


def _collect_and_place(console: Console, cwd: Path,
                       project_dir: Path | None, existing: dict | None) -> int:
    """采集 repo_url/来源并就位（direct_clone / template_init / 还没有仓库）。"""
    console.print("请输入仓库地址（git@... 或 https://...，留空表示还没有仓库）：")
    raw_url = console.input("repo_url> ").strip()

    # 留空表示还没有仓库：打开 github.com/new，回填后走 template_init
    if not raw_url:
        console.print("请在浏览器中创建空私仓，完成后回填 repo_url")
        _open_browser("https://github.com/new")
        console.print("请输入创建好的仓库地址：")
        raw2 = console.input("repo_url> ").strip()
        if not raw2:
            console.print("未回填仓库地址，已取消")
            return 1
        repo_url, _ = clean_repo_url(raw2)
        project_dir = cwd / _derive_project_dir_name(repo_url)
        return _do_template_init(console, project_dir, repo_url)

    try:
        repo_url, stripped = clean_repo_url(raw_url)
    except ValueError as exc:
        console.print(str(exc))
        return 1
    if stripped:
        console.print("检测到地址含鉴权段，已剥离；请改用 SSH key 或 HTTPS 凭据转发")

    console.print("仓库来源：direct_clone / template_init")
    source = console.input("来源> ").strip()

    if project_dir is None:
        project_dir = cwd / _derive_project_dir_name(repo_url)

    if source == "direct_clone":
        return _do_direct_clone(console, project_dir, repo_url)
    if source == "template_init":
        return _do_template_init(console, project_dir, repo_url)

    console.print(f"未知来源：{source}")
    return 1


def _do_direct_clone(console: Console, project_dir: Path, repo_url: str) -> int:
    """已关联好项目仓库：clone 就位。"""
    if project_dir.exists():
        if gitops.is_git_repo(project_dir) and _remote_matches(project_dir, repo_url):
            return _place_and_finalize(console, project_dir, repo_url,
                                       {"apply_strategy": "direct_clone", "should_push": False})
        console.print(f"目录已存在且非目标仓库：{project_dir}")
        return 1
    if not console.confirm(f"将 clone {repo_url} 到 {project_dir}？", default=True):
        console.print("已取消")
        return 1
    ok = gitops.clone(repo_url, project_dir)
    if not ok:
        console.print("clone 失败：请检查 SSH key / gh auth login / credential helper")
        return 1
    return _place_and_finalize(console, project_dir, repo_url,
                               {"apply_strategy": "direct_clone", "should_push": False})


def _do_template_init(console: Console, project_dir: Path, repo_url: str) -> int:
    """空仓库：clone 模板为 upstream，关联 origin，should_push=True。"""
    console.print("请输入模板仓库地址：")
    template_repo = console.input("template_repo> ").strip()
    console.print("请输入模板分支：")
    template_branch = console.input("template_branch> ").strip() or "main"

    if project_dir.exists():
        console.print(f"目录已存在且非目标仓库：{project_dir}")
        return 1
    if not console.confirm(f"将从 {template_repo} 初始化到 {project_dir}？", default=True):
        console.print("已取消")
        return 1
    ok = gitops.clone(template_repo, project_dir, origin="upstream")
    if not ok:
        console.print("模板 clone 失败：请检查 SSH key / gh auth login / credential helper")
        return 1
    gitops.checkout_set_upstream(project_dir, template_branch)
    gitops.remote_add(project_dir, "origin", repo_url)
    return _place_and_finalize(console, project_dir, repo_url, {
        "apply_strategy": "template_init", "should_push": True,
        "template_repo": template_repo, "template_branch": template_branch,
    })


def _remote_matches(d: Path, repo_url: str) -> bool:
    """判断 d 的 remote 是否含 repo_url。"""
    return repo_url in gitops.remotes(d).values()
