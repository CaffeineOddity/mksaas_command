"""tests.test_env_command — mksaas env 命令测试。"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from mksaas import state
from mksaas.commands import env as env_cmd
from mksaas.console import FakeConsole


def make_args(group=None, profile=None):
    return argparse.Namespace(
        command="env", version=False, group=group, profile=profile,
    )


def _seed_project(tmp_path):
    """在 tmp_path 内就位一个有效项目（含状态文件）。"""
    state.ensure_state_dir(tmp_path)
    sp = tmp_path / state.STATE_DIRNAME / state.STATE_FILENAME
    state.save(sp, state.init_default())
    return sp


def test_env_writes_to_profile_test(tmp_path, monkeypatch):
    """mksaas env core --profile test 写入 profiles.test。"""
    sp = _seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=["y", "https://localhost:3000"])  # 修改 + base url
    # 无已有值 → 直接采集
    c = FakeConsole(inputs=["https://localhost:3000"])
    rc = env_cmd.run_env(make_args("core", "test"), c)
    assert rc == 0
    data = state.load(sp)
    val = data["profiles"]["test"]["env_groups"]["core"]["NEXT_PUBLIC_BASE_URL"]
    assert val["value"] == "https://localhost:3000"


def test_env_kebab_group_maps_to_snake(tmp_path, monkeypatch):
    """连字符形式 github-oauth → github_oauth。"""
    sp = _seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=["id123"], secrets=["secret"])  # client_id input, client_secret getpass
    rc = env_cmd.run_env(make_args("github-oauth", "test"), c)
    assert rc == 0
    data = state.load(sp)
    grp = data["profiles"]["test"]["env_groups"]["github_oauth"]
    assert grp["GITHUB_CLIENT_ID"]["value"] == "id123"
    assert grp["GITHUB_CLIENT_SECRET"]["value"] == "secret"


def test_env_default_profile_is_test(tmp_path, monkeypatch):
    """缺省 profile → 默认 test。"""
    sp = _seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=["https://x.com"])
    rc = env_cmd.run_env(make_args("core", None), c)
    assert rc == 0
    data = state.load(sp)
    assert "core" in data["profiles"]["test"]["env_groups"]


def test_env_no_state_file_prompts_project(tmp_path, monkeypatch):
    """非项目目录（无状态文件）→提示先 mksaas project，不创建。"""
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[])
    rc = env_cmd.run_env(make_args("core", "test"), c)
    assert rc != 0
    assert any("mksaas project" in line for line in c.stdout)
    assert not (tmp_path / state.STATE_DIRNAME).exists()


def test_env_unknown_group_lists_available(tmp_path, monkeypatch):
    """未知 group→列出可用分组并退出非 0。"""
    _seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[])
    rc = env_cmd.run_env(make_args("nope", "test"), c)
    assert rc != 0
    assert any("core" in line for line in c.stdout)


def test_env_no_group_arg_lists_available(tmp_path, monkeypatch):
    """未给 group 参数→列出可用分组。"""
    _seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    c = FakeConsole(inputs=[])
    rc = env_cmd.run_env(make_args(None, "test"), c)
    assert rc != 0
    assert any("github-oauth" in line or "github_oauth" in line for line in c.stdout)
