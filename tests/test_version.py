"""tests.test_version — 版本管理与构建逻辑测试。"""

import json

import pytest

from mksaas import version


def test_read_version(tmp_path, monkeypatch):
    # 默认 build.config.json 由 build.sh 维护；测试用独立文件避免污染仓库配置
    vf = tmp_path / "build.config.json"
    vf.write_text(json.dumps({"version": "0.1.0", "build": 10}))
    v, b = version.read_version(vf)
    assert v == "0.1.0"
    assert b == 10


def test_read_version_invalid(tmp_path):
    vf = tmp_path / "build.config.json"
    vf.write_text("{not json")
    with pytest.raises(version.VersionError):
        version.read_version(vf)


def test_version_string_debug():
    assert version.version_string("0.1.0", 10, release=False) == "0.1.0-dev10"


def test_version_string_release():
    assert version.version_string("0.1.0", 10, release=True) == "0.1.0"


def test_bump_patch():
    v, b = version.bump("0.1.5", "patch")
    assert v == "0.1.6"
    assert b == 0


def test_bump_minor():
    v, b = version.bump("0.1.5", "minor")
    assert v == "0.2.0"
    assert b == 0


def test_bump_major():
    v, b = version.bump("1.2.3", "major")
    assert v == "2.0.0"
    assert b == 0


def test_bump_invalid_level():
    with pytest.raises(ValueError):
        version.bump("0.1.0", "weird")


def test_bump_invalid_version():
    with pytest.raises(ValueError):
        version.bump("0.1", "patch")


def test_write_version(tmp_path):
    vf = tmp_path / "build.config.json"
    vf.write_text(
        json.dumps({
            "app_name": "demo",
            "entry": "main.py",
            "version": "0.1.0",
            "build": 2,
        }),
        encoding="utf-8",
    )
    version.write_version(vf, "0.2.0", 0)
    data = json.loads(vf.read_text())
    assert data == {
        "app_name": "demo",
        "entry": "main.py",
        "version": "0.2.0",
        "build": 0,
    }


def test_parse_product_path_debug():
    assert version.product_path("dist", "0.1.0", 10, release=False) == "dist/0.1.0-dev10/mksaas"


def test_parse_product_path_release():
    assert version.product_path("dist", "0.1.0", 10, release=True) == "dist/0.1.0/mksaas"


def test_sort_version_strings():
    """版本字符串排序：dev10 > dev2；release 与 dev 同 version 时 dev 排后。"""
    items = ["0.1.0-dev2", "0.1.0-dev10", "0.1.0", "0.1.1-dev1"]
    s = sorted(items, key=version.sort_key)
    assert s[-1] == "0.1.1-dev1"
    assert s[0] == "0.1.0-dev2"
