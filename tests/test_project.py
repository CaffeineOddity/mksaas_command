"""tests.test_project — mksaas project 命令测试。

用 FakeConsole + monkeypatch gitops 验证各分支，不真正联网/clone。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from mksaas.commands import project as project_cmd
from mksaas.console import FakeConsole


def make_args(**kw):
    """构造 project 子命令的 argparse Namespace。"""
    base = {"command": "project", "version": False}
    base.update(kw)
    return argparse.Namespace(**base)


def _set_git_repo(d: Path, remote_url: str | None, remote_name: str = "origin"):
    """在 d 内建一个假 git 仓库（.git 目录 + remote）。"""
    (d / ".git").mkdir(parents=True)
    (d / ".git" / "config").write_text(
        f"[remote \"{remote_name}\"]\n\turl = {remote_url}\n\tfetch = +refs/heads/*:refs/remotes/{remote_name}/*\n"
    )


def test_existing_state_kept_on_keep(tmp_path, monkeypatch):
    """已有状态且用户沿用→不改 repo_url。"""
    from mksaas import state

    state_dir = state.ensure_state_dir(tmp_path)
    sp = state_dir / "setup-state.json"
    state.save(sp, state.init_default())
    data = state.load(sp)
    data["project"] = {"repo_url": "https://github.com/o/r.git",
                       "project_dir": str(tmp_path), "apply_strategy": "direct_clone"}
    state.save(sp, data)

    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=["n"])  # 不修改
    rc = project_cmd.run_project(make_args(), c)
    assert rc == 0
    after = state.load(sp)
    assert after["project"]["repo_url"] == "https://github.com/o/r.git"


def test_existing_local_from_cwd_git_repo(tmp_path, monkeypatch):
    """cwd 是 git 仓库→existing_local 分支，建 .mksaas，回写 project_dir。"""
    _set_git_repo(tmp_path, "https://github.com/o/r.git")
    monkeypatch.setattr(project_cmd.gitops, "is_git_repo", lambda d: d == tmp_path)
    monkeypatch.setattr(project_cmd.gitops, "remote_url",
                        lambda d, name="origin": "https://github.com/o/r.git" if d == tmp_path else None)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[])
    rc = project_cmd.run_project(make_args(), c)
    assert rc == 0
    from mksaas import state
    sp = state.locate_state_file(tmp_path)
    data = state.load(sp)
    assert data["project"]["repo_url"] == "https://github.com/o/r.git"
    assert data["project"]["apply_strategy"] == "existing_local"


def test_direct_clone(tmp_path, monkeypatch):
    """无状态非 git，来源 direct_clone→git clone 被调用且 URL 干净。"""
    calls = []
    def fake_clone(url, dst, origin=None):
        calls.append((url, dst, origin))
        _set_git_repo(dst, url)
        return True
    monkeypatch.setattr(project_cmd.gitops, "clone", fake_clone)
    monkeypatch.setattr(project_cmd.gitops, "is_git_repo", lambda d: False)

    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[
        "https://user:tok@github.com/o/r.git",  # repo_url（含鉴权段，应被剥离）
        "direct_clone",  # 仓库来源
        "y",  # 确认推导的 project_dir
    ])
    rc = project_cmd.run_project(make_args(), c)
    assert rc == 0
    # clone 收到的是干净 URL
    assert calls[0][0] == "https://github.com/o/r.git"
    from mksaas import state
    # 状态文件应落在 clone 出的项目目录内
    project_dir = Path(calls[0][1])
    sp = state.locate_state_file(project_dir)
    data = state.load(sp)
    assert data["project"]["repo_url"] == "https://github.com/o/r.git"
    assert data["project"]["apply_strategy"] == "direct_clone"


def test_template_init(tmp_path, monkeypatch):
    """来源 template_init→clone --origin upstream + remote add origin，should_push=True。"""
    calls = []
    def fake_clone(url, dst, origin=None):
        calls.append(("clone", url, dst, origin))
        _set_git_repo(dst, url, remote_name=origin or "origin")
        return True
    def fake_remote_add(d, name, url):
        calls.append(("remote_add", name, url))
    monkeypatch.setattr(project_cmd.gitops, "clone", fake_clone)
    monkeypatch.setattr(project_cmd.gitops, "remote_add", fake_remote_add)
    monkeypatch.setattr(project_cmd.gitops, "is_git_repo", lambda d: False)

    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[
        "https://github.com/o/myrepo.git",   # repo_url
        "template_init",                     # 来源
        "https://github.com/MkSaaSHQ/mksaas-template.git",  # template_repo
        "main",                              # template_branch
        "y",                                 # 确认 project_dir
    ])
    rc = project_cmd.run_project(make_args(), c)
    assert rc == 0
    from mksaas import state
    project_dir = tmp_path / "myrepo"
    sp = state.locate_state_file(project_dir)
    data = state.load(sp)
    assert data["project"]["apply_strategy"] == "template_init"
    assert data["project"]["should_push"] is True
    assert data["project"]["template_repo"] == "https://github.com/MkSaaSHQ/mksaas-template.git"
    # 验证 clone 用了 upstream 远程名
    clone_calls = [c for c in calls if c[0] == "clone"]
    assert clone_calls[0][3] == "upstream"


def test_no_repo_opens_browser(tmp_path, monkeypatch):
    """来源 还没有仓库→打开 github.com/new，回填后走 template_init。"""
    opened = []
    monkeypatch.setattr(project_cmd, "_open_browser", lambda url: opened.append(url))
    fake_clone_calls = []
    def fake_clone(url, dst, origin=None):
        fake_clone_calls.append((url, dst, origin))
        _set_git_repo(dst, url, remote_name=origin or "origin")
        return True
    monkeypatch.setattr(project_cmd.gitops, "clone", fake_clone)
    monkeypatch.setattr(project_cmd.gitops, "remote_add", lambda *a, **k: None)
    monkeypatch.setattr(project_cmd.gitops, "is_git_repo", lambda d: False)

    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[
        "",  # repo_url 留空 → 还没有仓库分支
        "https://github.com/o/newrepo.git",  # 用户回填的 repo_url
        "https://github.com/MkSaaSHQ/mksaas-template.git",  # template
        "main",  # branch
        "y",  # 确认 project_dir
    ])
    rc = project_cmd.run_project(make_args(), c)
    assert rc == 0
    assert opened == ["https://github.com/new"]


def test_dir_exists_non_target_raises(tmp_path, monkeypatch):
    """推导的 project_dir 已存在且非目标仓库→抛错中文提示。"""
    # 预先建一个同名目录但不是 git 仓库
    (tmp_path / "r").mkdir()
    monkeypatch.setattr(project_cmd.gitops, "is_git_repo", lambda d: False)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[
        "https://github.com/o/r.git",
        "direct_clone",
    ])
    rc = project_cmd.run_project(make_args(), c)
    assert rc != 0
    assert any("已存在" in line or "目录" in line for line in c.stdout)


def test_prompts_cd_after(tmp_path, monkeypatch):
    """结尾提示 cd 到 project_dir。"""
    _set_git_repo(tmp_path, "https://github.com/o/r.git")
    monkeypatch.setattr(project_cmd.gitops, "is_git_repo", lambda d: d == tmp_path)
    monkeypatch.setattr(project_cmd.gitops, "remote_url",
                        lambda d, name="origin": "https://github.com/o/r.git" if d == tmp_path else None)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[])
    project_cmd.run_project(make_args(), c)
    assert any("cd" in line and "mksaas env" in line for line in c.stdout)
