"""tests.test_apply — mksaas apply 命令测试。"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from mksaas import state
from mksaas.commands import apply as apply_cmd
from mksaas.console import FakeConsole
from mksaas.schema import load_schema


def make_args(profile=None, **kw):
    base = {"command": "apply", "version": False, "profile": profile}
    base.update(kw)
    return argparse.Namespace(**base)


def _fill_required(s, test_url="https://t.com", prod_url="https://p.com"):
    """填满 core / database / better_auth 三个必填分组。"""
    s["profiles"]["test"]["env_groups"]["core"] = {
        "NEXT_PUBLIC_BASE_URL": {"value": test_url, "source": "prompt",
                                 "required": True, "description": "x"}}
    s["profiles"]["prod"]["env_groups"]["core"] = {
        "NEXT_PUBLIC_BASE_URL": {"value": prod_url, "source": "prompt",
                                 "required": True, "description": "x"}}
    s["profiles"]["test"]["env_groups"]["database"] = {
        "DATABASE_URL": {"value": "postgres://t", "source": "prompt",
                         "required": True, "description": "x", "sensitive": True}}
    s["profiles"]["prod"]["env_groups"]["database"] = {
        "DATABASE_URL": {"value": "postgres://p", "source": "prompt",
                         "required": True, "description": "x", "sensitive": True}}
    s["profiles"]["test"]["env_groups"]["better_auth"] = {
        "BETTER_AUTH_SECRET": {"value": "testsecret", "source": "prompt",
                               "required": True, "description": "x", "sensitive": True,
                               "generate_if_empty": True}}
    s["profiles"]["prod"]["env_groups"]["better_auth"] = {
        "BETTER_AUTH_SECRET": {"value": "prodsecret", "source": "prompt",
                               "required": True, "description": "x", "sensitive": True,
                               "generate_if_empty": True}}


def _seed_project(tmp_path, project=True, core_filled=True):
    """就位项目；project=False 时省略 project 块。"""
    state.ensure_state_dir(tmp_path)
    sp = tmp_path / state.STATE_DIRNAME / state.STATE_FILENAME
    s = state.init_default()
    if project:
        s["project"] = {
            "repo_url": "https://github.com/o/r.git",
            "project_dir": str(tmp_path),
        }
    if core_filled:
        _fill_required(s)
    state.save(sp, s)
    return sp


def _patch_git_ok(monkeypatch):
    """让 apply 的 git 校验通过：当前目录是 git 仓库且 remote 含 repo_url。"""
    monkeypatch.setattr(apply_cmd.gitops, "is_git_repo", lambda d: True)
    monkeypatch.setattr(apply_cmd.gitops, "has_remote", lambda d, url: True)


def test_apply_missing_project_aborts(tmp_path, monkeypatch):
    """project 缺失→终止并提示先 mksaas project。"""
    _seed_project(tmp_path, project=False)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[])
    rc = apply_cmd.run_apply(make_args(), c)
    assert rc != 0
    assert any("mksaas project" in line for line in c.stdout)


def test_apply_no_state_aborts(tmp_path, monkeypatch):
    """无状态文件→提示先 project。"""
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[])
    rc = apply_cmd.run_apply(make_args(), c)
    assert rc != 0


def test_apply_required_missing_prompts(tmp_path, monkeypatch):
    """必填缺失→提示返回 env 补全，不写文件。"""
    _seed_project(tmp_path, core_filled=False)
    _patch_git_ok(monkeypatch)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[])
    rc = apply_cmd.run_apply(make_args("test"), c)
    assert rc != 0
    assert any("env" in line for line in c.stdout)
    assert not (tmp_path / ".mksaas" / ".env.test").exists()


def test_apply_required_missing_reports_profile(tmp_path, monkeypatch):
    """必填缺失→报错按 profile 区分，并提示 --profile <profile> 补全。"""
    _seed_project(tmp_path, core_filled=False)
    _patch_git_ok(monkeypatch)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[])
    rc = apply_cmd.run_apply(make_args("test"), c)
    assert rc != 0
    blob = "\n".join(c.stdout)
    assert "[test]" in blob
    assert "--profile test" in blob


def test_apply_test_only_not_blocked_by_empty_prod(tmp_path, monkeypatch):
    """--profile test：prod 未采集不阻断 test 的 apply。

    只填 test 必填，prod 留空。apply --profile test 应成功（不校验 prod 必填）。
    """
    sp = tmp_path / state.STATE_DIRNAME / state.STATE_FILENAME
    s = state.init_default()
    s["project"] = {"repo_url": "https://github.com/o/r.git", "project_dir": str(tmp_path)}
    # 只填 test 三个必填分组，prod 全空
    s["profiles"]["test"]["env_groups"]["core"] = {
        "NEXT_PUBLIC_BASE_URL": {"value": "https://t.com", "source": "prompt",
                                 "required": True, "description": "x"}}
    s["profiles"]["test"]["env_groups"]["database"] = {
        "DATABASE_URL": {"value": "postgres://t", "source": "prompt",
                         "required": True, "description": "x", "sensitive": True}}
    s["profiles"]["test"]["env_groups"]["better_auth"] = {
        "BETTER_AUTH_SECRET": {"value": "sec", "source": "prompt",
                               "required": True, "description": "x", "sensitive": True,
                               "generate_if_empty": True}}
    state.save(sp, s)
    _patch_git_ok(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(apply_cmd.gitops, "push", lambda *a, **k: (True, ""))
    c = FakeConsole(inputs=["y"])
    rc = apply_cmd.run_apply(make_args("test"), c)
    assert rc == 0
    root = (tmp_path / ".env").read_text()
    assert "NEXT_PUBLIC_BASE_URL=https://t.com" in root


def test_apply_profile_prod_validates_prod(tmp_path, monkeypatch):
    """--profile prod：prod 缺必填→终止；test 是否齐全不影响。"""
    sp = tmp_path / state.STATE_DIRNAME / state.STATE_FILENAME
    s = state.init_default()
    s["project"] = {"repo_url": "https://github.com/o/r.git", "project_dir": str(tmp_path)}
    # test 齐，prod 空
    s["profiles"]["test"]["env_groups"]["core"] = {
        "NEXT_PUBLIC_BASE_URL": {"value": "https://t.com", "source": "prompt",
                                 "required": True, "description": "x"}}
    state.save(sp, s)
    _patch_git_ok(monkeypatch)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[])
    rc = apply_cmd.run_apply(make_args("prod"), c)
    assert rc != 0
    blob = "\n".join(c.stdout)
    assert "[prod]" in blob
    assert "--profile prod" in blob


def test_apply_default_profile_is_test(tmp_path, monkeypatch):
    """缺省 --profile → 默认 test。"""
    sp = _seed_project(tmp_path)  # 两 profile 都齐
    _patch_git_ok(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(apply_cmd.gitops, "push", lambda *a, **k: (True, ""))
    c = FakeConsole(inputs=["y"])
    rc = apply_cmd.run_apply(make_args(None), c)
    assert rc == 0
    assert state.load(sp)["apply"]["last_profile"] == "test"


def test_apply_check_dir_mismatch_aborts(tmp_path, monkeypatch):
    """project_dir 与 cwd 不一致→check 终止。"""
    other = tmp_path / "elsewhere"
    other.mkdir()
    _seed_project(other)  # 状态文件在 other 内，project_dir=other
    # 复制状态文件到 cwd(tmp_path)，使 locate 能找到，但 project_dir 仍指向 other
    src_sp = other / state.STATE_DIRNAME / state.STATE_FILENAME
    cwd_sp = tmp_path / state.STATE_DIRNAME / state.STATE_FILENAME
    cwd_sp.parent.mkdir(parents=True, exist_ok=True)
    cwd_sp.write_text(src_sp.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)  # cwd 是 tmp_path，与 project_dir=other 不一致
    c = FakeConsole(inputs=[])
    rc = apply_cmd.run_apply(make_args(), c)
    assert rc != 0
    assert any("不一致" in line or "cd" in line for line in c.stdout)


def test_apply_check_not_git_repo_aborts(tmp_path, monkeypatch):
    """项目目录非 git 仓库→check 终止。"""
    _seed_project(tmp_path)
    monkeypatch.setattr(apply_cmd.gitops, "is_git_repo", lambda d: False)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[])
    rc = apply_cmd.run_apply(make_args(), c)
    assert rc != 0
    assert any("git 仓库" in line for line in c.stdout)


def test_apply_check_remote_mismatch_aborts(tmp_path, monkeypatch):
    """项目目录 remote 不含 repo_url→check 终止。"""
    _seed_project(tmp_path)
    monkeypatch.setattr(apply_cmd.gitops, "is_git_repo", lambda d: True)
    monkeypatch.setattr(apply_cmd.gitops, "has_remote", lambda d, url: False)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[])
    rc = apply_cmd.run_apply(make_args(), c)
    assert rc != 0
    assert any("非同一仓库" in line or "remote" in line for line in c.stdout)


def test_apply_rebuilds_and_syncs(tmp_path, monkeypatch):
    """确认执行→重建 .env.test/.env.prod + 同步根 .env。"""
    sp = _seed_project(tmp_path)
    _patch_git_ok(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(apply_cmd.gitops, "push", lambda *a, **k: (True, ""))
    c = FakeConsole(inputs=["y"])  # 确认执行（test profile 由 --profile 决定，无同步追问）
    rc = apply_cmd.run_apply(make_args("test"), c)
    assert rc == 0
    assert (tmp_path / ".mksaas" / ".env.test").exists()
    assert (tmp_path / ".mksaas" / ".env.prod").exists()
    root = (tmp_path / ".env").read_text()
    assert "NEXT_PUBLIC_BASE_URL=https://t.com" in root


def test_apply_always_pushes(tmp_path, monkeypatch):
    """apply 完一律尝试 push（不再读 should_push）。"""
    _seed_project(tmp_path)
    _patch_git_ok(monkeypatch)
    monkeypatch.chdir(tmp_path)
    pushed = []
    monkeypatch.setattr(apply_cmd.gitops, "push",
                        lambda *a, **k: pushed.append(True) or (True, ""))
    c = FakeConsole(inputs=["y"])
    apply_cmd.run_apply(make_args("test"), c)
    assert len(pushed) == 1


def test_apply_push_nonfastforward_prompts(tmp_path, monkeypatch):
    """push non-fast-forward→提示手动 pull --rebase，不阻断（rc==0）。"""
    _seed_project(tmp_path)
    _patch_git_ok(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(apply_cmd.gitops, "push",
                        lambda *a, **k: (False, "! [rejected] main -> main (non-fast-forward)"))
    c = FakeConsole(inputs=["y"])
    rc = apply_cmd.run_apply(make_args("test"), c)
    assert rc == 0  # apply 仍完成
    assert any("non-fast-forward" in line or "pull --rebase" in line for line in c.stdout)


def test_apply_push_auth_failure_prompts(tmp_path, monkeypatch):
    """push 鉴权失败→中文提示检查凭据，不重试注入。"""
    _seed_project(tmp_path)
    _patch_git_ok(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(apply_cmd.gitops, "push",
                        lambda *a, **k: (False, "Permission denied (publickey)"))
    c = FakeConsole(inputs=["y"])
    rc = apply_cmd.run_apply(make_args("test"), c)
    assert rc == 0  # apply 本身仍完成（文件已落地）
    assert any("凭据" in line or "SSH" in line or "gh auth" in line for line in c.stdout)


def test_apply_writes_steps_and_next_steps(tmp_path, monkeypatch):
    """回写 steps.apply 与生成 SETUP_NEXT_STEPS.md。"""
    sp = _seed_project(tmp_path)
    _patch_git_ok(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(apply_cmd.gitops, "push", lambda *a, **k: (True, ""))
    c = FakeConsole(inputs=["y"])
    apply_cmd.run_apply(make_args("test"), c)
    data = state.load(sp)
    assert data["steps"]["apply"]["status"] == "completed"
    assert data["steps"]["apply"]["applied"] is True
    assert data["apply"]["push_result"] == "success"
    assert data["apply"]["last_profile"] == "test"
    assert (tmp_path / "SETUP_NEXT_STEPS.md").is_file()


def test_apply_summary_masks_secrets(tmp_path, monkeypatch):
    """摘要中不出现完整密钥。"""
    sp = _seed_project(tmp_path)
    s = state.load(sp)
    secret_val = "supersecrettoken1234567890"
    s["profiles"]["test"]["env_groups"]["github_oauth"] = {
        "GITHUB_CLIENT_SECRET": {"value": secret_val, "source": "prompt",
                                 "required": False, "description": "x", "sensitive": True}}
    s["profiles"]["prod"]["env_groups"]["github_oauth"] = {
        "GITHUB_CLIENT_SECRET": {"value": secret_val, "source": "prompt",
                                 "required": False, "description": "x", "sensitive": True}}
    state.save(sp, s)
    _patch_git_ok(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(apply_cmd.gitops, "push", lambda *a, **k: (True, ""))
    c = FakeConsole(inputs=["n"])  # 不执行，仅看摘要
    apply_cmd.run_apply(make_args("test"), c)
    blob = "\n".join(c.stdout)
    assert secret_val not in blob
