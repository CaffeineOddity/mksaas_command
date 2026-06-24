"""tests.test_apply — mksaas apply 命令测试。"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from mksaas import state
from mksaas.commands import apply as apply_cmd
from mksaas.console import FakeConsole
from mksaas.schema import load_schema


def make_args(**kw):
    base = {"command": "apply", "version": False}
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
            "apply_strategy": "existing_local",
            "should_push": False,
        }
    if core_filled:
        _fill_required(s)
    state.save(sp, s)
    return sp


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
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[])
    rc = apply_cmd.run_apply(make_args(), c)
    assert rc != 0
    assert any("env" in line for line in c.stdout)
    assert not (tmp_path / ".mksaas" / ".env.test").exists()


def test_apply_rebuilds_and_syncs(tmp_path, monkeypatch):
    """确认执行→重建 .env.test/.env.prod + 同步根 .env。"""
    sp = _seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(apply_cmd.gitops, "push", lambda *a, **k: (True, ""))
    c = FakeConsole(inputs=["y", "test"])  # 确认执行 + 选 test 同步
    rc = apply_cmd.run_apply(make_args(), c)
    assert rc == 0
    assert (tmp_path / ".mksaas" / ".env.test").exists()
    assert (tmp_path / ".mksaas" / ".env.prod").exists()
    root = (tmp_path / ".env").read_text()
    assert "NEXT_PUBLIC_BASE_URL=https://t.com" in root


def test_apply_should_push_false_skips_push(tmp_path, monkeypatch):
    """should_push=False→跳过 push。"""
    _seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    pushed = []
    monkeypatch.setattr(apply_cmd.gitops, "push",
                        lambda *a, **k: pushed.append(True) or (True, ""))
    c = FakeConsole(inputs=["y", "test"])
    apply_cmd.run_apply(make_args(), c)
    assert pushed == []  # should_push=False 不 push


def test_apply_should_push_true_pushes(tmp_path, monkeypatch):
    """should_push=True 且 repo_url 非空→push 被调用。"""
    sp = _seed_project(tmp_path)
    # 改成 should_push=True
    s = state.load(sp)
    s["project"]["should_push"] = True
    state.save(sp, s)
    monkeypatch.chdir(tmp_path)
    pushed = []
    monkeypatch.setattr(apply_cmd.gitops, "push",
                        lambda *a, **k: pushed.append(args_of(a, k)) or (True, ""))
    c = FakeConsole(inputs=["y", "test"])
    apply_cmd.run_apply(make_args(), c)
    assert len(pushed) == 1


def args_of(a, k):
    return (a, k)


def test_apply_empty_repo_url_treats_no_push(tmp_path, monkeypatch):
    """repo_url 空→should_push 视为假，跳过 push。"""
    sp = _seed_project(tmp_path)
    s = state.load(sp)
    s["project"]["should_push"] = True
    s["project"]["repo_url"] = ""
    state.save(sp, s)
    monkeypatch.chdir(tmp_path)
    pushed = []
    monkeypatch.setattr(apply_cmd.gitops, "push",
                        lambda *a, **k: pushed.append(True) or (True, ""))
    c = FakeConsole(inputs=["y", "test"])
    apply_cmd.run_apply(make_args(), c)
    assert pushed == []


def test_apply_push_auth_failure_prompts(tmp_path, monkeypatch):
    """push 鉴权失败→中文提示检查凭据，不重试注入。"""
    sp = _seed_project(tmp_path)
    s = state.load(sp)
    s["project"]["should_push"] = True
    state.save(sp, s)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(apply_cmd.gitops, "push",
                        lambda *a, **k: (False, "Permission denied (publickey)"))
    c = FakeConsole(inputs=["y", "test"])
    rc = apply_cmd.run_apply(make_args(), c)
    assert rc == 0  # apply 本身仍完成（文件已落地）
    assert any("凭据" in line or "SSH" in line or "gh auth" in line for line in c.stdout)


def test_apply_writes_steps_and_next_steps(tmp_path, monkeypatch):
    """回写 steps.apply 与生成 SETUP_NEXT_STEPS.md。"""
    sp = _seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(apply_cmd.gitops, "push", lambda *a, **k: (True, ""))
    c = FakeConsole(inputs=["y", "test"])
    apply_cmd.run_apply(make_args(), c)
    data = state.load(sp)
    assert data["steps"]["apply"]["status"] == "completed"
    assert data["steps"]["apply"]["applied"] is True
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
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(apply_cmd.gitops, "push", lambda *a, **k: (True, ""))
    c = FakeConsole(inputs=["n"])  # 不执行，仅看摘要
    apply_cmd.run_apply(make_args(), c)
    blob = "\n".join(c.stdout)
    assert secret_val not in blob
