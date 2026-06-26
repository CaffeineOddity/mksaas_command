"""tests.test_prompts — 通用环境分组采集交互测试。

collect_group 每次采集单个 profile：每行变量预填当前值/默认值，
留空=保留，输入新值=覆盖。敏感字段走 getpass。
"""

from __future__ import annotations

import pytest

from mksaas import prompts, state
from mksaas.console import FakeConsole


def _fresh_state():
    return state.init_default()


def test_collect_group_modify_non_sensitive(tmp_path, monkeypatch):
    """采集 core/test：输入 URL；URL 校验。"""
    s = _fresh_state()
    c = FakeConsole(inputs=["https://example.com"])
    changed = prompts.collect_group(s, "core", "test", c)
    assert changed is True
    val = s["profiles"]["test"]["env_groups"]["core"]["NEXT_PUBLIC_BASE_URL"]
    assert val["value"] == "https://example.com"
    assert val["source"] == "prompt"


def test_collect_group_invalid_url_reprompts(tmp_path, monkeypatch):
    """必填 URL 非法→提示重新输入。"""
    s = _fresh_state()
    c = FakeConsole(inputs=["not-a-url", "https://ok.com"])
    prompts.collect_group(s, "core", "test", c)
    val = s["profiles"]["test"]["env_groups"]["core"]["NEXT_PUBLIC_BASE_URL"]["value"]
    assert val == "https://ok.com"


def test_collect_group_sensitive_uses_getpass(tmp_path, monkeypatch):
    """敏感字段走 getpass；prod 采集一个 secret。"""
    s = _fresh_state()
    c = FakeConsole(inputs=["id_p"], secrets=["gh_secret_prod"])
    prompts.collect_group(s, "github_oauth", "prod", c)
    grp = s["profiles"]["prod"]["env_groups"]["github_oauth"]
    assert grp["GITHUB_CLIENT_ID"]["value"] == "id_p"
    assert grp["GITHUB_CLIENT_SECRET"]["value"] == "gh_secret_prod"
    assert grp["GITHUB_CLIENT_SECRET"]["source"] == "prompt"


def test_collect_group_optional_empty_kept(tmp_path, monkeypatch):
    """非必填留空→保留默认（github_oauth 无默认→空）。"""
    s = _fresh_state()
    # client_id 留空(input) + client_secret 留空(getpass)
    c = FakeConsole(inputs=[""], secrets=[""])
    prompts.collect_group(s, "github_oauth", "test", c)
    grp = s["profiles"]["test"]["env_groups"]["github_oauth"]
    assert grp["GITHUB_CLIENT_ID"]["value"] == ""
    assert grp["GITHUB_CLIENT_SECRET"]["value"] == ""


def test_collect_group_better_auth_generate(tmp_path, monkeypatch):
    """BETTER_AUTH_SECRET 空+自动生成→确认生成，source=prompt_or_generate。"""
    s = _fresh_state()
    # getpass 空 → 确认自动生成(y)
    c = FakeConsole(inputs=["y"], secrets=[""])
    prompts.collect_group(s, "better_auth", "test", c)
    val = s["profiles"]["test"]["env_groups"]["better_auth"]["BETTER_AUTH_SECRET"]
    assert val["value"] and len(val["value"]) >= 32
    assert val["source"] == "prompt_or_generate"


def test_collect_group_keep_default_when_empty(tmp_path, monkeypatch):
    """有 schema 默认值的变量留空→保留默认值。"""
    s = _fresh_state()
    # storage 6 变量：4 非敏感 input + 2 敏感 getpass
    c = FakeConsole(inputs=["", "", "", ""], secrets=["", ""])
    prompts.collect_group(s, "storage", "test", c)
    region = s["profiles"]["test"]["env_groups"]["storage"]["STORAGE_REGION"]
    assert region["value"] == "auto"
    assert region["source"] == "default"
