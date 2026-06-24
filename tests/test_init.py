"""tests.test_init — mksaas init 编排器测试。"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from mksaas import state
from mksaas.commands import init as init_cmd
from mksaas.console import FakeConsole


def make_args():
    return argparse.Namespace(command="init", version=False)


def _seed_project(tmp_path):
    """就位一个有效项目目录，返回其路径与状态文件。"""
    state.ensure_state_dir(tmp_path)
    sp = tmp_path / state.STATE_DIRNAME / state.STATE_FILENAME
    s = state.init_default()
    s["project"] = {"repo_url": "https://github.com/o/r.git",
                    "project_dir": str(tmp_path),
                    "apply_strategy": "existing_local", "should_push": False}
    s["steps"]["project"]["status"] = "completed"
    # 填满必填
    for prof, url in (("test", "https://t.com"), ("prod", "https://p.com")):
        s["profiles"][prof]["env_groups"]["core"] = {
            "NEXT_PUBLIC_BASE_URL": {"value": url, "source": "prompt",
                                     "required": True, "description": "x"}}
        s["profiles"][prof]["env_groups"]["database"] = {
            "DATABASE_URL": {"value": "postgres://x", "source": "prompt",
                             "required": True, "description": "x", "sensitive": True}}
        s["profiles"][prof]["env_groups"]["better_auth"] = {
            "BETTER_AUTH_SECRET": {"value": "sec", "source": "prompt",
                                   "required": True, "description": "x", "sensitive": True,
                                   "generate_if_empty": True}}
    state.save(sp, s)
    return tmp_path, sp


def test_init_project_mandatory_cannot_skip(tmp_path, monkeypatch):
    """project 必填不可跳；拒绝→终止。"""
    monkeypatch.chdir(tmp_path)
    # 无状态文件 → init 调 project；project 采集时空 repo_url 再空回填 → 取消
    c = FakeConsole(inputs=["", ""])
    rc = init_cmd.run_init(make_args(), c)
    assert rc != 0


def test_init_runs_env_groups_skippable(tmp_path, monkeypatch):
    """逐个 env 分组可处理或跳过；跳过记 env_groups_skipped。"""
    proj_dir, sp = _seed_project(tmp_path)
    monkeypatch.chdir(proj_dir)

    # 用桩替换 project/env/apply 的实际执行
    called = {"env": [], "apply": False}
    monkeypatch.setattr(init_cmd, "_run_project_step", lambda console: 0)
    monkeypatch.setattr(init_cmd, "_run_env_step",
                        lambda gid, console: called["env"].append(gid) or 0)
    monkeypatch.setattr(init_cmd, "_run_apply_step",
                        lambda console: called.__setitem__("apply", True) or 0)

    # 对每个分组：确认处理(第一个) / 跳过(其余)
    from mksaas.groups import groups_in_order
    n = len(groups_in_order())
    inputs = []
    inputs.append("y")  # 处理 core
    for _ in range(n - 1):
        inputs.append("n")  # 跳过其余
    inputs.append("n")  # apply 前确认 → 暂不执行

    c = FakeConsole(inputs=inputs)
    rc = init_cmd.run_init(make_args(), c)
    assert rc == 0
    assert called["env"] == ["core"]
    assert called["apply"] is False
    data = state.load(sp)
    skipped = data["steps"]["init"]["env_groups_skipped"]
    assert "database" in skipped  # 其余被跳过


def test_init_apply_confirm_runs_apply(tmp_path, monkeypatch):
    """apply 前确认 yes→执行 apply。"""
    proj_dir, sp = _seed_project(tmp_path)
    monkeypatch.chdir(proj_dir)
    monkeypatch.setattr(init_cmd, "_run_project_step", lambda console: 0)
    monkeypatch.setattr(init_cmd, "_run_env_step", lambda gid, console: 0)
    ran = {"apply": False}
    monkeypatch.setattr(init_cmd, "_run_apply_step",
                        lambda console: ran.__setitem__("apply", True) or 0)

    from mksaas.groups import groups_in_order
    inputs = ["n"] * len(groups_in_order())  # 全部跳过
    inputs.append("y")  # apply 确认 yes
    c = FakeConsole(inputs=inputs)
    rc = init_cmd.run_init(make_args(), c)
    assert rc == 0
    assert ran["apply"] is True


def test_init_resume_progress(tmp_path, monkeypatch):
    """续跑：已有 steps.init 进度时从断点继续。"""
    proj_dir, sp = _seed_project(tmp_path)
    # 预置：core 已处理，其余待处理
    s = state.load(sp)
    s["steps"]["init"]["env_groups_processed"] = ["core"]
    state.save(sp, s)
    monkeypatch.chdir(proj_dir)
    monkeypatch.setattr(init_cmd, "_run_project_step", lambda console: 0)
    called = []
    monkeypatch.setattr(init_cmd, "_run_env_step",
                        lambda gid, console: called.append(gid) or 0)
    monkeypatch.setattr(init_cmd, "_run_apply_step", lambda console: 0)

    from mksaas.groups import groups_in_order
    remaining = [g for g in groups_in_order() if g != "core"]
    inputs = ["n"] * len(remaining)  # 跳过所有剩余
    inputs.append("n")  # apply 暂不
    c = FakeConsole(inputs=inputs)
    init_cmd.run_init(make_args(), c)
    # core 不应被再次处理
    assert "core" not in called


def test_init_summary_masks_secrets(tmp_path, monkeypatch):
    """摘要不泄露密钥。"""
    proj_dir, sp = _seed_project(tmp_path)
    monkeypatch.chdir(proj_dir)
    monkeypatch.setattr(init_cmd, "_run_project_step", lambda console: 0)
    monkeypatch.setattr(init_cmd, "_run_env_step", lambda gid, console: 0)
    monkeypatch.setattr(init_cmd, "_run_apply_step", lambda console: 0)

    from mksaas.groups import groups_in_order
    inputs = ["n"] * len(groups_in_order())
    inputs.append("n")
    c = FakeConsole(inputs=inputs)
    init_cmd.run_init(make_args(), c)
    blob = "\n".join(c.stdout)
    assert "postgres://x" not in blob  # database url 不泄露
