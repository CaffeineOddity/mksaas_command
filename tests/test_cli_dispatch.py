"""tests.test_cli_dispatch — CLI 分发测试。"""

import subprocess

from mksaas import __version__
from mksaas.cli import build_parser, main
from mksaas.console import FakeConsole


def test_version_prints_and_exits_zero():
    c = FakeConsole()
    rc = main(["--version"], console=c)
    assert rc == 0
    assert c.stdout[-1] == f"mksaas {__version__}"


def test_no_command_exits_nonzero():
    c = FakeConsole()
    rc = main([], console=c)
    assert rc == 1


def test_unknown_command_is_unimplemented():
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
