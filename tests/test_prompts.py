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
    # 1=暂不配置，2=Neon，3=Supabase → getpass 输入 DATABASE_URL（敏感字段）
    c = FakeConsole(inputs=["2"], secrets=["postgresql://neon.example/db"])
    changed = prompts.collect_group(s, "database", "test", c)
    assert changed is True
    assert opened == ["https://neon.com/"]
    val = s["profiles"]["test"]["env_groups"]["database"]["DATABASE_URL"]
    assert val["value"] == "postgresql://neon.example/db"
    assert val["source"] == "prompt"


def test_collect_database_skip_clears_group(tmp_path, monkeypatch):
    """database 选「暂不配置数据库」→ 清空分组。"""
    s = _fresh_state()
    monkeypatch.setattr(prompts.webbrowser, "open", lambda url: None)
    # 1=暂不配置数据库
    c = FakeConsole(inputs=["1"])
    changed = prompts.collect_group(s, "database", "test", c)
    assert changed is True
    assert s["profiles"]["test"]["env_groups"]["database"] == {}


def test_collect_database_supabase_writes(tmp_path, monkeypatch):
    """database 选 Supabase → 打开网页 → 输入 URL → 写入。"""
    s = _fresh_state()
    opened = []
    monkeypatch.setattr(prompts.webbrowser, "open", lambda url: opened.append(url))
    # 1=暂不配置，2=Neon，3=Supabase → getpass 输入 DATABASE_URL
    c = FakeConsole(inputs=["3"], secrets=["postgresql://supabase.example/db"])
    changed = prompts.collect_group(s, "database", "test", c)
    assert changed is True
    assert opened == ["https://supabase.com/"]
    val = s["profiles"]["test"]["env_groups"]["database"]["DATABASE_URL"]
    assert val["value"] == "postgresql://supabase.example/db"
    assert val["source"] == "prompt"


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
    # 11=Clarity（Vercel Analytics 在第 10 位）
    c = FakeConsole(inputs=["11", "clarity-123"])
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


def test_collect_newsletter_resend_writes_provider(tmp_path, monkeypatch):
    """newsletter 选 Resend → 打开网页 → 自动写 NEWSLETTER_PROVIDER=resend，无额外变量。"""
    s = _fresh_state()
    opened = []
    monkeypatch.setattr(prompts.webbrowser, "open", lambda url: opened.append(url))
    # 1=Resend，2=Beehiiv，3=跳过/手动输入
    c = FakeConsole(inputs=["1"])
    changed = prompts.collect_group(s, "newsletter", "test", c)
    assert changed is True
    assert opened == ["https://resend.com/"]
    grp = s["profiles"]["test"]["env_groups"]["newsletter"]
    assert grp["NEWSLETTER_PROVIDER"]["value"] == "resend"
    assert grp["NEWSLETTER_PROVIDER"]["source"] == "prompt"
    assert "BEEHIIV_API_KEY" not in grp
    assert "BEEHIIV_PUBLICATION_ID" not in grp


def test_collect_newsletter_beehiiv_writes(tmp_path, monkeypatch):
    """newsletter 选 Beehiiv → 打开网页 → 采集 BEEHIIV_API_KEY + PUBLICATION_ID + 自动写 provider。"""
    s = _fresh_state()
    opened = []
    monkeypatch.setattr(prompts.webbrowser, "open", lambda url: opened.append(url))
    # 1=Resend，2=Beehiiv，3=跳过/手动输入 → BEEHIIV_API_KEY（敏感=secrets），BEEHIIV_PUBLICATION_ID（普通=inputs）
    c = FakeConsole(inputs=["2", "pub-123"], secrets=["beehiiv-key-abc"])
    changed = prompts.collect_group(s, "newsletter", "test", c)
    assert changed is True
    assert opened == ["https://beehiiv.com/"]
    grp = s["profiles"]["test"]["env_groups"]["newsletter"]
    assert grp["NEWSLETTER_PROVIDER"]["value"] == "beehiiv"
    assert grp["BEEHIIV_API_KEY"]["value"] == "beehiiv-key-abc"
    assert grp["BEEHIIV_PUBLICATION_ID"]["value"] == "pub-123"


def test_collect_newsletter_skip_falls_back_to_full_profile(tmp_path, monkeypatch):
    """newsletter 选跳过 → 回退到完整 _collect_profile 采集全部变量。"""
    s = _fresh_state()
    monkeypatch.setattr(prompts.webbrowser, "open", lambda url: None)
    # 3=跳过/手动输入，走完整 profile → 3 个变量：NEWSLETTER_PROVIDER（普通），BEEHIIV_API_KEY（敏感），BEEHIIV_PUBLICATION_ID（普通）
    c = FakeConsole(inputs=["3", "resend", "pub-123"], secrets=["sk-beehiiv"])
    changed = prompts.collect_group(s, "newsletter", "test", c)
    assert changed is True
    grp = s["profiles"]["test"]["env_groups"]["newsletter"]
    assert grp["NEWSLETTER_PROVIDER"]["value"] == "resend"
    assert grp["BEEHIIV_API_KEY"]["value"] == "sk-beehiiv"
    assert grp["BEEHIIV_PUBLICATION_ID"]["value"] == "pub-123"


# ── 参考控制测试（smoke）──
# 按 collect_group 代码路径拆分，改哪条路径就跑对应的那条。
# 跑法：pytest tests/test_prompts.py -k "smoke_" -xvs   # 全部
#       pytest tests/test_prompts.py -k "smoke_collect_profile_generic" -xvs  # 单条


def test_smoke_collect_profile_generic():
    """smoke: 通用 _collect_profile 路径（core 分组）。"""
    s = _fresh_state()
    c = FakeConsole(inputs=["https://smoke.example.com"])
    assert prompts.collect_group(s, "core", "test", c) is True
    assert s["profiles"]["test"]["env_groups"]["core"]["NEXT_PUBLIC_BASE_URL"]["value"] == "https://smoke.example.com"


def test_smoke_collect_provider_subset():
    """smoke: _collect_provider_subset 路径（database，同 analytics/notification/affiliate/ai）。"""
    s = _fresh_state()
    c = FakeConsole(inputs=["2"], secrets=["postgresql://smoke.example/db"])
    assert prompts.collect_group(s, "database", "test", c) is True
    assert s["profiles"]["test"]["env_groups"]["database"]["DATABASE_URL"]["value"] == "postgresql://smoke.example/db"


def test_smoke_collect_custom_provider():
    """smoke: 自定义 provider + 自动写 provider 值（newsletter，同 payment 模式）。"""
    s = _fresh_state()
    c = FakeConsole(inputs=["1"])
    assert prompts.collect_group(s, "newsletter", "test", c) is True
    assert s["profiles"]["test"]["env_groups"]["newsletter"]["NEWSLETTER_PROVIDER"]["value"] == "resend"


def test_smoke_collect_guided():
    """smoke: _collect_guided 路径（captcha，同 storage/email/github_oauth/google_oauth）。"""
    s = _fresh_state()
    c = FakeConsole(inputs=["smoke-site-key"], secrets=["smoke-secret-key"])
    assert prompts.collect_group(s, "captcha", "test", c) is True
    grp = s["profiles"]["test"]["env_groups"]["captcha"]
    assert grp["NEXT_PUBLIC_TURNSTILE_SITE_KEY"]["value"] == "smoke-site-key"
    assert grp["TURNSTILE_SECRET_KEY"]["value"] == "smoke-secret-key"
