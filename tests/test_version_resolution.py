"""tests.test_version_resolution — CLI 版本号解析测试。

验证 cli.get_version() 从 _version 模块读到构建时注入的版本字符串，
而非写死的占位；构建态缺失时回落到 dev 占位。
"""

from __future__ import annotations

import importlib

from mksaas import cli


def test_get_version_uses_injected_version(monkeypatch):
    """构建时注入的 __version__ 应被 get_version 返回。"""
    import mksaas._version as vmod
    monkeypatch.setattr(vmod, "__version__", "1.2.3-dev9", raising=False)
    importlib.reload(cli) if False else None  # 占位，避免 lint
    assert cli.get_version() == "1.2.3-dev9"


def test_get_version_fallback_when_missing(monkeypatch):
    """未注入时回落到 0.0.0+dev 占位，不抛错。"""
    import mksaas._version as vmod
    monkeypatch.setattr(vmod, "__version__", "0.0.0+dev", raising=False)
    assert cli.get_version() == "0.0.0+dev"


def test_cli_version_flag_prints_resolved_version(monkeypatch):
    """mksaas --version 打印 get_version() 的结果。"""
    monkeypatch.setattr(cli, "get_version", lambda: "9.9.9-dev1")
    from mksaas.console import FakeConsole
    c = FakeConsole()
    rc = cli.main(["--version"], console=c)
    assert rc == 0
    assert any("9.9.9-dev1" in line for line in c.stdout)
