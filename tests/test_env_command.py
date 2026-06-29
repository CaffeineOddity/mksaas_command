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
    """mksaas env core --profile test 只采集 test。"""
    sp = _seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
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
    opened = []
    monkeypatch.setattr("mksaas.prompts.webbrowser.open",
                        lambda u: opened.append(u))
    c = FakeConsole(inputs=["id123"], secrets=["secret"])
    rc = env_cmd.run_env(make_args("github-oauth", "test"), c)
    assert rc == 0
    data = state.load(sp)
    grp = data["profiles"]["test"]["env_groups"]["github_oauth"]
    assert grp["GITHUB_CLIENT_ID"]["value"] == "id123"
    assert grp["GITHUB_CLIENT_SECRET"]["value"] == "secret"
    assert opened == ["https://github.com/settings/applications/new"]


def test_env_github_oauth_opens_apply_url(tmp_path, monkeypatch):
    """github-oauth 采集时打开 github.com/settings/applications/new，并提示回调 URL。"""
    _seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    opened = []
    monkeypatch.setattr("mksaas.prompts.webbrowser.open",
                        lambda u: opened.append(u))
    c = FakeConsole(inputs=["id123"], secrets=["secret"])
    rc = env_cmd.run_env(make_args("github-oauth", "test"), c)
    assert rc == 0
    assert opened == ["https://github.com/settings/applications/new"]
    blob = "\n".join(c.stdout)
    assert "/api/auth/callback/github" in blob


def test_env_google_oauth_opens_apply_url(tmp_path, monkeypatch):
    """google-oauth 采集时打开 Google Cloud Console 凭据页，并提示回调 URL。"""
    _seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    opened = []
    monkeypatch.setattr("mksaas.prompts.webbrowser.open",
                        lambda u: opened.append(u))
    c = FakeConsole(inputs=["gid"], secrets=["gsecret"])
    rc = env_cmd.run_env(make_args("google-oauth", "test"), c)
    assert rc == 0
    assert opened == ["https://console.cloud.google.com/apis/credentials"]
    blob = "\n".join(c.stdout)
    assert "/api/auth/callback/google" in blob


def test_env_oauth_callback_uses_base_url(tmp_path, monkeypatch):
    """已采集 core 的 base_url 时，oauth 回调 URL 拼出完整地址。"""
    sp = _seed_project(tmp_path)
    s = state.load(sp)
    s["profiles"]["test"]["env_groups"]["core"] = {
        "NEXT_PUBLIC_BASE_URL": {"value": "https://example.com", "source": "prompt"}}
    state.save(sp, s)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("mksaas.prompts.webbrowser.open", lambda u: None)
    c = FakeConsole(inputs=["id"], secrets=["sec"])
    env_cmd.run_env(make_args("github-oauth", "test"), c)
    blob = "\n".join(c.stdout)
    assert "https://example.com/api/auth/callback/github" in blob


def test_env_storage_opens_r2_dashboard(tmp_path, monkeypatch):
    """storage 采集时打开 Cloudflare R2 dashboard，打印创建步骤，6 字段写入。"""
    sp = _seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    opened = []
    monkeypatch.setattr("mksaas.prompts.webbrowser.open",
                        lambda u: opened.append(u))
    # 变量顺序：REGION(input) / BUCKET_NAME(input) / ACCESS_KEY_ID(secret) /
    #          SECRET_ACCESS_KEY(secret) / ENDPOINT(input) / PUBLIC_URL(input)
    c = FakeConsole(
        inputs=["auto", "my-bucket", "https://abc.r2.cloudflarestorage.com",
                "https://cdn.example.com"],
        secrets=["AKIDxxx", "SECRETxxx"],
    )
    rc = env_cmd.run_env(make_args("storage", "test"), c)
    assert rc == 0
    assert opened == ["https://dash.cloudflare.com/?to=/:account/r2"]
    blob = "\n".join(c.stdout)
    assert "Create User API Token" in blob
    assert "r2.cloudflarestorage.com" in blob

    data = state.load(sp)
    grp = data["profiles"]["test"]["env_groups"]["storage"]
    assert grp["STORAGE_REGION"]["value"] == "auto"
    assert grp["STORAGE_BUCKET_NAME"]["value"] == "my-bucket"
    assert grp["STORAGE_ACCESS_KEY_ID"]["value"] == "AKIDxxx"
    assert grp["STORAGE_ACCESS_KEY_ID"]["sensitive"] is True
    assert grp["STORAGE_SECRET_ACCESS_KEY"]["value"] == "SECRETxxx"
    assert grp["STORAGE_SECRET_ACCESS_KEY"]["sensitive"] is True
    assert grp["STORAGE_ENDPOINT"]["value"] == "https://abc.r2.cloudflarestorage.com"
    assert grp["STORAGE_PUBLIC_URL"]["value"] == "https://cdn.example.com"


def test_env_default_profile_is_test(tmp_path, monkeypatch):
    """缺省 profile → 默认 test，只采集 test。"""
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


def test_env_payment_stripe_provider(tmp_path, monkeypatch):
    """payment 选 Stripe → 打开 Stripe 控制台，仅采集 Stripe 变量，PROVIDER 自动写 stripe。"""
    sp = _seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    opened = []
    monkeypatch.setattr("mksaas.prompts.webbrowser.open",
                        lambda u: opened.append(u))
    # choose 选 Stripe(1)；变量顺序（敏感走 secrets，非敏感走 inputs）：
    # STRIPE_SECRET_KEY(secret) / STRIPE_WEBHOOK_SECRET(secret) /
    # PRICE_PRO_MONTHLY / _YEARLY / _LIFETIME / CREDITS_BASIC / _STANDARD / _PREMIUM / _ENTERPRISE
    c = FakeConsole(
        inputs=["1",
                "price_m", "price_y", "price_life",
                "price_cb", "price_cs", "price_cp", "price_ce"],
        secrets=["sk_test_xxx", "whsec_xxx"],
    )
    rc = env_cmd.run_env(make_args("payment", "test"), c)
    assert rc == 0
    assert opened == ["https://dashboard.stripe.com/"]
    blob = "\n".join(c.stdout)
    assert "/api/webhooks/stripe" in blob

    data = state.load(sp)
    grp = data["profiles"]["test"]["env_groups"]["payment"]
    assert grp["VITE_PAYMENT_PROVIDER"]["value"] == "stripe"
    assert grp["STRIPE_SECRET_KEY"]["value"] == "sk_test_xxx"
    assert grp["STRIPE_SECRET_KEY"]["sensitive"] is True
    assert grp["STRIPE_WEBHOOK_SECRET"]["value"] == "whsec_xxx"
    assert grp["NEXT_PUBLIC_STRIPE_PRICE_PRO_MONTHLY"]["value"] == "price_m"
    assert grp["NEXT_PUBLIC_STRIPE_PRICE_CREDITS_ENTERPRISE"]["value"] == "price_ce"
    # 仅采集 Stripe 子集，Creem 变量不应出现
    assert "CREEM_API_KEY" not in grp
    assert "VITE_CREEM_PRODUCT_PRO_MONTHLY" not in grp


def test_env_payment_creem_provider(tmp_path, monkeypatch):
    """payment 选 Creem → 打开 creem.io，仅采集 Creem 变量，PROVIDER 自动写 creem。"""
    sp = _seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    opened = []
    monkeypatch.setattr("mksaas.prompts.webbrowser.open",
                        lambda u: opened.append(u))
    # choose 选 Creem(2)；变量顺序：
    # CREEM_API_KEY(secret) / CREEM_WEBHOOK_SECRET(secret) /
    # VITE_CREEM_PRODUCT_PRO_MONTHLY / _PRO_YEARLY / _LIFETIME
    c = FakeConsole(
        inputs=["2", "prod_m", "prod_y", "prod_life"],
        secrets=["creem_test_xxx", "whsec_creem"],
    )
    rc = env_cmd.run_env(make_args("payment", "test"), c)
    assert rc == 0
    assert opened == ["https://creem.io/"]
    blob = "\n".join(c.stdout)
    assert "/api/webhooks/creem" in blob

    data = state.load(sp)
    grp = data["profiles"]["test"]["env_groups"]["payment"]
    assert grp["VITE_PAYMENT_PROVIDER"]["value"] == "creem"
    assert grp["CREEM_API_KEY"]["value"] == "creem_test_xxx"
    assert grp["CREEM_API_KEY"]["sensitive"] is True
    assert grp["CREEM_WEBHOOK_SECRET"]["value"] == "whsec_creem"
    assert grp["VITE_CREEM_PRODUCT_PRO_MONTHLY"]["value"] == "prod_m"
    assert grp["VITE_CREEM_PRODUCT_LIFETIME"]["value"] == "prod_life"
    # 仅采集 Creem 子集，Stripe 变量不应出现
    assert "STRIPE_SECRET_KEY" not in grp
    assert "NEXT_PUBLIC_STRIPE_PRICE_PRO_MONTHLY" not in grp
