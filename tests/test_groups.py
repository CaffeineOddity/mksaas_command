"""tests.test_groups — 分组标识符映射测试。"""

import pytest

from mksaas.groups import (
    group_kebab_to_snake,
    group_snake_to_kebab,
    groups_in_order,
)


def test_groups_in_order_fixed():
    ids = groups_in_order()
    assert ids == [
        "core", "database", "better_auth", "github_oauth", "google_oauth",
        "email", "newsletter", "storage", "payment", "configurations", "analytics",
        "notification", "affiliate", "captcha", "crisp", "cron_jobs", "ai",
        "firecrawl",
    ]


def test_kebab_to_snake():
    assert group_kebab_to_snake("github-oauth") == "github_oauth"
    assert group_kebab_to_snake("cron-jobs") == "cron_jobs"
    assert group_kebab_to_snake("core") == "core"


def test_snake_to_kebab():
    assert group_snake_to_kebab("github_oauth") == "github-oauth"
    assert group_snake_to_kebab("core") == "core"


def test_roundtrip():
    for g in groups_in_order():
        assert group_kebab_to_snake(group_snake_to_kebab(g)) == g


def test_unknown_kebab_raises():
    with pytest.raises(KeyError):
        group_kebab_to_snake("nope-thing")
