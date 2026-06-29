"""tests.test_schema — env-schema.yaml 加载测试。"""

import pytest

from mksaas.schema import SchemaError, find_group, load_schema


def test_load_schema_returns_18_groups_in_order():
    groups = load_schema()
    ids = [g["id"] for g in groups]
    assert ids == [
        "core", "database", "better_auth", "github_oauth", "google_oauth",
        "email", "newsletter", "storage", "payment", "configurations", "analytics",
        "notification", "affiliate", "captcha", "crisp", "cron_jobs", "ai",
        "firecrawl",
    ]
    # order 字段升序
    orders = [g["order"] for g in groups]
    assert orders == sorted(orders)


def test_each_variable_has_required_fields():
    for g in load_schema():
        for v in g["variables"]:
            for field in ("name", "required", "test_default", "prod_default",
                          "generate_if_empty", "sensitive", "description"):
                assert field in v, f"{g['id']}/{v.get('name')} 缺 {field}"


def test_find_group():
    g = find_group("cron_jobs")
    names = [v["name"] for v in g["variables"]]
    assert names == ["CRON_JOBS_USERNAME", "CRON_JOBS_PASSWORD"]


def test_find_group_unknown_raises():
    with pytest.raises(KeyError):
        find_group("nope")


def test_better_auth_generate_if_empty():
    g = find_group("better_auth")
    v = g["variables"][0]
    assert v["name"] == "BETTER_AUTH_SECRET"
    assert v["generate_if_empty"] is True
    assert v["sensitive"] is True
