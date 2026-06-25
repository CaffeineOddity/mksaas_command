"""tests.test_cli_dispatch — CLI 分发测试。"""

import subprocess

from mksaas import paths
from mksaas.cli import build_parser, main
from mksaas.console import FakeConsole


def test_version_prints_and_exits_zero():
    c = FakeConsole()
    rc = main(["--version"], console=c)
    assert rc == 0
    assert any("mksaas" in line for line in c.stdout)


def test_no_command_exits_nonzero():
    c = FakeConsole()
    rc = main([], console=c)
    assert rc == 1


def test_unknown_command_is_unimplemented():
    # 全部子命令已实现；这里验证 --version 与无命令分支已覆盖。
    # 用一个未注册的伪命令走 argparse 报错路径。
    import pytest
    with pytest.raises(SystemExit):
        main(["bogus-subcommand"], console=FakeConsole())


def test_top_level_help_mentions_common_commands():
    """顶层帮助应展示常用命令提示。"""
    help_text = build_parser().format_help()
    assert "常用命令" in help_text
    assert "mksaas env github-oauth --profile prod" in help_text


def test_env_help_mentions_examples_and_profile():
    """env 帮助应展示示例与 profile 说明。"""
    out = subprocess.run(
        ["python3", "-m", "mksaas", "env", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    help_text = out.stdout + out.stderr
    assert "usage: mksaas env <group> [--profile <test | prod>] [-h]" in help_text
    assert "环境分组名称" in help_text
    assert "core" in help_text
    assert "基础站点 URL 与回调地址" in help_text
    assert "github-oauth" in help_text
    assert "GitHub 登录配置" in help_text
    assert "firecrawl" in help_text
    assert "Firecrawl 抓取配置" in help_text
    assert "示例" in help_text
    assert "mksaas env core" in help_text
    assert "mksaas env github-oauth --profile prod" in help_text
    assert "目标 profile（test 或 prod）" in help_text


def test_version_prefers_installed_product_metadata(monkeypatch):
    """已安装发布产物时，--version 应优先显示安装版本。"""
    monkeypatch.setattr(
        paths,
        "install_metadata",
        lambda: {"installed_from": "0.1.0-dev2", "repo_root": "/tmp/repo"},
    )
    c = FakeConsole()
    rc = main(["--version"], console=c)
    assert rc == 0
    assert c.stdout[-1] == "mksaas 0.1.0-dev2"


def test_version_falls_back_to_repo_version(monkeypatch, tmp_path):
    """源码态无已安装产物时，--version 应读取仓库 build.config.json。"""
    version_file = tmp_path / "build.config.json"
    version_file.write_text(
        '{"app_name": "demo", "entry": "main.py", "version": "0.2.0", "build": 7}',
        encoding="utf-8",
    )
    monkeypatch.setattr(paths, "install_metadata", lambda: {})
    monkeypatch.setattr(paths, "repo_root", lambda: tmp_path)
    c = FakeConsole()
    rc = main(["--version"], console=c)
    assert rc == 0
    assert c.stdout[-1] == "mksaas 0.2.0-dev7"
