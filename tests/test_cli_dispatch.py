"""tests.test_cli_dispatch — CLI 分发测试。"""

from mksaas.cli import main
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
