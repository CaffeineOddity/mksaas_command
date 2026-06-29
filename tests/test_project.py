"""tests.test_project — mksaas project 命令测试。

用 FakeConsole + monkeypatch gitops 验证各分支，不真正联网/clone。
新就位模型：二选一菜单（已有仓库地址 / 没有仓库，新建仓库）→ clone → 检测空/非空分流。
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
    (d / ".git").mkdir(parents=True, exist_ok=True)
    (d / ".git" / "config").write_text(
        f"[remote \"{remote_name}\"]\n\turl = {remote_url}\n\tfetch = +refs/heads/{remote_name}/*:refs/remotes/{remote_name}/*\n"
    )


def test_existing_state_kept_on_keep(tmp_path, monkeypatch):
    """已有状态且用户沿用→不改 repo_url，无策略标记。"""
    from mksaas import state

    state_dir = state.ensure_state_dir(tmp_path)
    sp = state_dir / "setup-state.json"
    state.save(sp, state.init_default())
    data = state.load(sp)
    data["project"] = {"repo_url": "https://github.com/o/r.git",
                       "project_dir": str(tmp_path)}
    state.save(sp, data)

    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=["n"])  # 不修改
    rc = project_cmd.run_project(make_args(), c)
    assert rc == 0
    after = state.load(sp)
    assert after["project"]["repo_url"] == "https://github.com/o/r.git"
    assert "apply_strategy" not in after["project"]
    assert "should_push" not in after["project"]


def test_existing_state_modify_reenters_collect(tmp_path, monkeypatch):
    """已有状态且用户要修改→重新进采集流（选已有仓库地址，输入新 url）。"""
    from mksaas import state

    state.ensure_state_dir(tmp_path)
    sp = tmp_path / state.STATE_DIRNAME / state.STATE_FILENAME
    s = state.init_default()
    s["project"] = {"repo_url": "https://github.com/o/old.git", "project_dir": str(tmp_path)}
    state.save(sp, s)

    # monkeypatch：cwd 视为已就位的 git 仓库（避免再 clone）；修改后走 §7.5 内容分流
    monkeypatch.setattr(project_cmd.gitops, "is_git_repo", lambda d: d == tmp_path)
    monkeypatch.setattr(project_cmd.gitops, "remote_url",
                        lambda d, name="origin": "https://github.com/o/old.git" if d == tmp_path else None)
    monkeypatch.setattr(project_cmd.gitops, "has_commits", lambda d: True)
    monkeypatch.chdir(tmp_path)

    c = FakeConsole(inputs=["y"])  # 确认修改
    rc = project_cmd.run_project(make_args(), c)
    assert rc == 0
    sp = tmp_path / state.STATE_DIRNAME / state.STATE_FILENAME
    after = state.load(sp)
    assert after["project"]["repo_url"] == "https://github.com/o/old.git"
    assert "apply_strategy" not in after["project"]


def test_cwd_git_repo_dispatches_by_content(tmp_path, monkeypatch):
    """cwd 是 git 仓库→从 remote 推断 repo_url，不 clone，按内容分流（有内容→§7.3）。"""
    from mksaas import state

    _set_git_repo(tmp_path, "https://github.com/o/r.git")
    monkeypatch.setattr(project_cmd.gitops, "is_git_repo", lambda d: d == tmp_path)
    monkeypatch.setattr(project_cmd.gitops, "remote_url",
                        lambda d, name="origin": "https://github.com/o/r.git" if d == tmp_path else None)
    monkeypatch.setattr(project_cmd.gitops, "has_commits", lambda d: True)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[])
    rc = project_cmd.run_project(make_args(), c)
    assert rc == 0
    sp = state.locate_state_file(tmp_path)
    data = state.load(sp)
    assert data["project"]["repo_url"] == "https://github.com/o/r.git"
    assert data["project"]["project_dir"] == str(tmp_path)
    assert "apply_strategy" not in data["project"]


def test_already_has_repo_url_input(tmp_path, monkeypatch):
    """选「已有仓库地址」→输入含鉴权段 url→clone 收到干净 url→非空→建状态，无策略标记。"""
    from mksaas import state

    calls = []
    def fake_clone(url, dst, origin=None):
        calls.append((url, dst, origin))
        _set_git_repo(dst, url)
        return True
    monkeypatch.setattr(project_cmd.gitops, "clone", fake_clone)
    monkeypatch.setattr(project_cmd.gitops, "is_git_repo", lambda d: False)
    monkeypatch.setattr(project_cmd.gitops, "has_remote",
                        lambda d, url: url in calls and Path(d).name == "r")
    monkeypatch.setattr(project_cmd.gitops, "has_commits", lambda d: True)

    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[
        "1",  # 选择「已有仓库地址」
        "https://user:tok@github.com/o/r.git",  # repo_url（含鉴权段，应被剥离）
        "y",  # 确认 clone
    ])
    rc = project_cmd.run_project(make_args(), c)
    assert rc == 0
    # clone 收到的是干净 URL
    assert calls[0][0] == "https://github.com/o/r.git"
    project_dir = Path(calls[0][1])
    sp = state.locate_state_file(project_dir)
    data = state.load(sp)
    assert data["project"]["repo_url"] == "https://github.com/o/r.git"
    assert data["project"]["repo_name"] == "r"
    assert "apply_strategy" not in data["project"]
    assert "should_push" not in data["project"]


def test_no_repo_opens_browser(tmp_path, monkeypatch):
    """选「没有仓库」→打开 github.com/new→回填 url→检测空仓→模板 clone。"""
    from mksaas import state

    opened = []
    monkeypatch.setattr(project_cmd, "_open_browser", lambda url: opened.append(url))
    clone_calls = []
    def fake_clone(url, dst, origin=None):
        clone_calls.append((url, dst, origin))
        _set_git_repo(dst, url, remote_name=origin or "origin")
        return True
    monkeypatch.setattr(project_cmd.gitops, "clone", fake_clone)
    monkeypatch.setattr(project_cmd.gitops, "remote_add", lambda *a, **k: None)
    monkeypatch.setattr(project_cmd.gitops, "checkout_set_upstream", lambda *a, **k: True)
    monkeypatch.setattr(project_cmd.gitops, "is_git_repo", lambda d: False)
    # 第一次 clone（用户空仓）→ has_commits False；模板 clone 后不再走分流
    monkeypatch.setattr(project_cmd.gitops, "has_commits", lambda d: False)
    monkeypatch.setattr(project_cmd.gitops, "has_remote", lambda d, url: False)
    # rmtree：仅删空目录占位（假仓库只有 .git，rmtree 能安全删）
    monkeypatch.setattr(project_cmd.shutil, "rmtree", lambda p, **k: None)

    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[
        "2",  # 选择「没有仓库，新建仓库」
        "https://github.com/o/newrepo.git",  # 回填 repo_url
        "y",  # 确认 clone 用户空仓
        "https://github.com/MkSaaSHQ/mksaas-template.git",  # template_repo
        "main",  # template_branch
        "y",  # 确认模板 clone
    ])
    rc = project_cmd.run_project(make_args(), c)
    assert rc == 0
    assert opened == ["https://github.com/new"]
    # 用户空仓先被 clone，检测为空后模板 clone；模板 clone 用了 upstream
    template_clone = clone_calls[-1]
    assert template_clone[0] == "https://github.com/MkSaaSHQ/mksaas-template.git"
    assert template_clone[2] == "upstream"
    project_dir = tmp_path / "newrepo"
    sp = state.locate_state_file(project_dir)
    data = state.load(sp)
    assert data["project"]["template_repo"] == "https://github.com/MkSaaSHQ/mksaas-template.git"
    assert data["project"]["template_branch"] == "main"


def test_dir_exists_other_repo_not_overwritten(tmp_path, monkeypatch):
    """推导的 project_dir 是另一个 git 仓库（remote 不匹配）→不覆盖，非 0。"""
    other = tmp_path / "r"
    _set_git_repo(other, "https://github.com/someoneelse/else.git")
    monkeypatch.setattr(project_cmd.gitops, "is_git_repo",
                        lambda d: d == other)
    monkeypatch.setattr(project_cmd.gitops, "has_remote", lambda d, url: False)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[
        "1",  # 已有仓库地址
        "https://github.com/o/r.git",
    ])
    rc = project_cmd.run_project(make_args(), c)
    assert rc != 0
    assert any("另一个仓库" in line or "不覆盖" in line for line in c.stdout)


def test_dir_exists_non_git_not_overwritten(tmp_path, monkeypatch):
    """project_dir 是普通目录（非 git）→不覆盖，非 0。"""
    (tmp_path / "r").mkdir()
    monkeypatch.setattr(project_cmd.gitops, "is_git_repo", lambda d: False)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[
        "1",  # 已有仓库地址
        "https://github.com/o/r.git",
    ])
    rc = project_cmd.run_project(make_args(), c)
    assert rc != 0
    assert any("非 git" in line or "不覆盖" in line for line in c.stdout)


def test_clone_reuse_same_repo(tmp_path, monkeypatch):
    """project_dir 已存在且是同一仓库→复用，不重新 clone。"""
    from mksaas import state

    project_dir = tmp_path / "r"
    _set_git_repo(project_dir, "https://github.com/o/r.git")
    monkeypatch.setattr(project_cmd.gitops, "is_git_repo", lambda d: d == project_dir)
    monkeypatch.setattr(project_cmd.gitops, "has_remote",
                        lambda d, url: url == "https://github.com/o/r.git")
    monkeypatch.setattr(project_cmd.gitops, "has_commits", lambda d: True)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[
        "1",  # 已有仓库地址
        "https://github.com/o/r.git",
    ])
    rc = project_cmd.run_project(make_args(), c)
    assert rc == 0
    sp = state.locate_state_file(project_dir)
    assert state.load(sp)["project"]["repo_url"] == "https://github.com/o/r.git"


def test_prompts_cd_after(tmp_path, monkeypatch):
    """结尾提示 cd 到 project_dir。"""
    from mksaas import state

    _set_git_repo(tmp_path, "https://github.com/o/r.git")
    monkeypatch.setattr(project_cmd.gitops, "is_git_repo", lambda d: d == tmp_path)
    monkeypatch.setattr(project_cmd.gitops, "remote_url",
                        lambda d, name="origin": "https://github.com/o/r.git" if d == tmp_path else None)
    monkeypatch.setattr(project_cmd.gitops, "has_commits", lambda d: True)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[])
    project_cmd.run_project(make_args(), c)
    assert any("cd" in line and "mksaas env" in line for line in c.stdout)
