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


def test_collect_database_provider_writes(tmp_path, monkeypatch):
    """database 选 Neon → 打开网页 → 输入 URL → 写入。"""
    s = _fresh_state()
    opened = []
    monkeypatch.setattr(prompts.webbrowser, "open", lambda url: opened.append(url))
    # choose 选 Neon(1) → getpass 输入 DATABASE_URL
    c = FakeConsole(inputs=["1"], secrets=["postgresql://neon.example/db"])
    changed = prompts.collect_group(s, "database", "test", c)
    assert changed is True
    assert opened == ["https://neon.com/"]
    val = s["profiles"]["test"]["env_groups"]["database"]["DATABASE_URL"]
    assert val["value"] == "postgresql://neon.example/db"
    assert val["source"] == "prompt"


def test_collect_database_empty_cancel(tmp_path, monkeypatch):
    """database 空输入 → 确认放弃 → 不写入，回到分组菜单。"""
    s = _fresh_state()
    monkeypatch.setattr(prompts.webbrowser, "open", lambda url: None)
    # choose 选 Supabase(2) → getpass 空 → confirm 确认放弃(y)
    c = FakeConsole(inputs=["2", "y"], secrets=[""])
    changed = prompts.collect_group(s, "database", "test", c)
    assert changed is False
    assert "database" not in s["profiles"]["test"]["env_groups"]


def test_collect_database_empty_retry_then_input(tmp_path, monkeypatch):
    """database 空输入 → 不放弃(n) → 重新输入 URL。"""
    s = _fresh_state()
    monkeypatch.setattr(prompts.webbrowser, "open", lambda url: None)
    # choose 选 Neon(1) → getpass 空 → confirm 不放弃(n) → getpass 输入
    c = FakeConsole(inputs=["1", "n"], secrets=["", "postgresql://retry.example/db"])
    changed = prompts.collect_group(s, "database", "test", c)
    assert changed is True
    val = s["profiles"]["test"]["env_groups"]["database"]["DATABASE_URL"]
    assert val["value"] == "postgresql://retry.example/db"


def test_collect_database_manual_skip_provider(tmp_path, monkeypatch):
    """database 选「跳过/手动输入」→ 不开网页 → 输入 URL。"""
    s = _fresh_state()
    opened = []
    monkeypatch.setattr(prompts.webbrowser, "open", lambda url: opened.append(url))
    # choose 选 跳过(3) → getpass 输入
    c = FakeConsole(inputs=["3"], secrets=["postgresql://manual.example/db"])
    changed = prompts.collect_group(s, "database", "test", c)
    assert changed is True
    assert opened == []
    val = s["profiles"]["test"]["env_groups"]["database"]["DATABASE_URL"]
    assert val["value"] == "postgresql://manual.example/db"


def test_collect_analytics_only_selected_provider(tmp_path, monkeypatch):
    """analytics 先选 provider，再只采集对应字段。"""
    s = _fresh_state()
    opened = []
    monkeypatch.setattr(prompts.webbrowser, "open", lambda url: opened.append(url))
    # 1=暂不启用，2=Google Analytics，3=Umami
    c = FakeConsole(inputs=["3", "umami-site-id", ""])
    changed = prompts.collect_group(s, "analytics", "test", c)
    assert changed is True
    assert opened == ["https://cloud.umami.is/"]
    grp = s["profiles"]["test"]["env_groups"]["analytics"]
    assert grp["NEXT_PUBLIC_UMAMI_WEBSITE_ID"]["value"] == "umami-site-id"
    assert grp["NEXT_PUBLIC_UMAMI_SCRIPT"]["value"] == "https://cloud.umami.is/script.js"
    assert grp["NEXT_PUBLIC_UMAMI_SCRIPT"]["source"] == "default"
    assert "NEXT_PUBLIC_GOOGLE_ANALYTICS_ID" not in grp
    assert "NEXT_PUBLIC_POSTHOG_KEY" not in grp


def test_collect_analytics_switch_provider_clears_old_fields(tmp_path, monkeypatch):
    """analytics 切换 provider 时，旧 provider 字段应被清理。"""
    s = _fresh_state()
    s["profiles"]["test"]["env_groups"]["analytics"] = {
        "NEXT_PUBLIC_UMAMI_WEBSITE_ID": {
            "value": "old-umami",
            "source": "prompt",
            "required": False,
            "description": "Umami website ID",
        },
        "NEXT_PUBLIC_UMAMI_SCRIPT": {
            "value": "https://cloud.umami.is/script.js",
            "source": "default",
            "required": False,
            "description": "Umami script URL",
        },
    }
    monkeypatch.setattr(prompts.webbrowser, "open", lambda url: None)
    # 10=Clarity
    c = FakeConsole(inputs=["10", "clarity-123"])
    changed = prompts.collect_group(s, "analytics", "test", c)
    assert changed is True
    grp = s["profiles"]["test"]["env_groups"]["analytics"]
    assert grp["NEXT_PUBLIC_CLARITY_PROJECT_ID"]["value"] == "clarity-123"
    assert "NEXT_PUBLIC_UMAMI_WEBSITE_ID" not in grp
    assert "NEXT_PUBLIC_UMAMI_SCRIPT" not in grp


def test_collect_notification_only_selected_channel(tmp_path, monkeypatch):
    """notification 先选渠道，再只采集对应 webhook。"""
    s = _fresh_state()
    opened = []
    monkeypatch.setattr(prompts.webbrowser, "open", lambda url: opened.append(url))
    # 1=暂不启用，2=Discord，3=Feishu
    c = FakeConsole(inputs=["3"], secrets=["https://open.feishu.cn/webhook/abc"])
    changed = prompts.collect_group(s, "notification", "test", c)
    assert changed is True
    assert opened == ["https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot"]
    grp = s["profiles"]["test"]["env_groups"]["notification"]
    assert grp["FEISHU_WEBHOOK_URL"]["value"] == "https://open.feishu.cn/webhook/abc"
    assert grp["FEISHU_WEBHOOK_URL"]["sensitive"] is True
    assert "DISCORD_WEBHOOK_URL" not in grp


def test_collect_affiliate_only_selected_provider(tmp_path, monkeypatch):
    """affiliate 先选 provider，再只采集对应公开 ID。"""
    s = _fresh_state()
    opened = []
    monkeypatch.setattr(prompts.webbrowser, "open", lambda url: opened.append(url))
    # 1=暂不启用，2=Affonso，3=PromoteKit
    c = FakeConsole(inputs=["2", "affonso-public-id"])
    changed = prompts.collect_group(s, "affiliate", "test", c)
    assert changed is True
    assert opened == ["https://affonso.io/"]
    grp = s["profiles"]["test"]["env_groups"]["affiliate"]
    assert grp["NEXT_PUBLIC_AFFILIATE_AFFONSO_ID"]["value"] == "affonso-public-id"
    assert "NEXT_PUBLIC_AFFILIATE_PROMOTEKIT_ID" not in grp


def test_collect_ai_switch_provider_clears_old_fields(tmp_path, monkeypatch):
    """ai 切换 provider 时，旧 provider 密钥应被清理。"""
    s = _fresh_state()
    s["profiles"]["test"]["env_groups"]["ai"] = {
        "OPENAI_API_KEY": {
            "value": "old-openai-key",
            "source": "prompt",
            "required": False,
            "description": "OpenAI API key",
            "sensitive": True,
        }
    }
    opened = []
    monkeypatch.setattr(prompts.webbrowser, "open", lambda url: opened.append(url))
    # 1=暂不启用，2=AI Gateway，3=FAL，4=Fireworks，5=OpenAI，6=Replicate，7=Google Generative AI
    c = FakeConsole(inputs=["7"], secrets=["gemini-key-123"])
    changed = prompts.collect_group(s, "ai", "test", c)
    assert changed is True
    assert opened == ["https://aistudio.google.com/app/apikey"]
    grp = s["profiles"]["test"]["env_groups"]["ai"]
    assert grp["GOOGLE_GENERATIVE_AI_API_KEY"]["value"] == "gemini-key-123"
    assert grp["GOOGLE_GENERATIVE_AI_API_KEY"]["sensitive"] is True
    assert "OPENAI_API_KEY" not in grp
