"""tests.test_prompts — 通用环境分组采集交互测试。"""

from __future__ import annotations

import pytest

from mksaas import prompts, state
from mksaas.console import FakeConsole


def _fresh_state():
    s = state.init_default()
    return s


def test_collect_group_keep_existing(tmp_path, monkeypatch):
    """已有值→展示（敏感 mask）→沿用→标记已采集。"""
    s = _fresh_state()
    s["profiles"]["test"]["env_groups"]["core"] = {
        "NEXT_PUBLIC_BASE_URL": {
            "value": "http://localhost:3000", "source": "prompt",
            "required": True, "description": "应用基础 URL",
        }
    }
    c = FakeConsole(inputs=["n"])  # 不修改
    changed = prompts.collect_group(s, "core", "test", c)
    assert changed is False
    val = s["profiles"]["test"]["env_groups"]["core"]["NEXT_PUBLIC_BASE_URL"]["value"]
    assert val == "http://localhost:3000"


def test_collect_group_modify_non_sensitive(tmp_path, monkeypatch):
    """修改→逐项输入（非敏感走 input）；URL 校验。"""
    s = _fresh_state()
    c = FakeConsole(inputs=[
        "y",  # 修改
        "https://example.com",  # NEXT_PUBLIC_BASE_URL
    ])
    changed = prompts.collect_group(s, "core", "test", c)
    assert changed is True
    val = s["profiles"]["test"]["env_groups"]["core"]["NEXT_PUBLIC_BASE_URL"]
    assert val["value"] == "https://example.com"
    assert val["source"] == "prompt"


def test_collect_group_invalid_url_reprompts(tmp_path, monkeypatch):
    """必填 URL 非法→提示重新输入。"""
    s = _fresh_state()
    c = FakeConsole(inputs=[
        "y",  # 修改
        "not-a-url",
        "https://ok.com",
    ])
    prompts.collect_group(s, "core", "test", c)
    val = s["profiles"]["test"]["env_groups"]["core"]["NEXT_PUBLIC_BASE_URL"]["value"]
    assert val == "https://ok.com"


def test_collect_group_sensitive_uses_getpass(tmp_path, monkeypatch):
    """敏感字段走 getpass。"""
    s = _fresh_state()
    c = FakeConsole(inputs=["y"], secrets=["gh_secret_123"])
    prompts.collect_group(s, "github_oauth", "test", c)
    val = s["profiles"]["test"]["env_groups"]["github_oauth"]["GITHUB_CLIENT_SECRET"]
    assert val["value"] == "gh_secret_123"
    assert val["source"] == "prompt"


def test_collect_group_optional_empty_kept(tmp_path, monkeypatch):
    """非必填留空→保留空（敏感字段走 getpass，需提供空 secret）。"""
    s = _fresh_state()
    # 无已有值时直接进入采集；inputs: client_id 留空; secrets: client_secret 留空
    c = FakeConsole(inputs=[""], secrets=[""])
    prompts.collect_group(s, "github_oauth", "test", c)
    grp = s["profiles"]["test"]["env_groups"]["github_oauth"]
    assert grp["GITHUB_CLIENT_ID"]["value"] == ""
    assert grp["GITHUB_CLIENT_SECRET"]["value"] == ""


def test_collect_group_better_auth_generate(tmp_path, monkeypatch):
    """BETTER_AUTH_SECRET 空+自动生成→调 secrets_gen，source=prompt_or_generate。"""
    s = _fresh_state()
    # 无已有值直接采集；getpass 返回空（留空），随后确认自动生成
    c = FakeConsole(inputs=["y"], secrets=[""])
    prompts.collect_group(s, "better_auth", "test", c)
    val = s["profiles"]["test"]["env_groups"]["better_auth"]["BETTER_AUTH_SECRET"]
    assert val["value"]
    assert len(val["value"]) >= 32
    assert val["source"] == "prompt_or_generate"
