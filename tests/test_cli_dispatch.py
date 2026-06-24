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
    # argparse 对未知子命令本身报错；这里用一个已注册但未实现的命令验证分发。
    c = FakeConsole()
    rc = main(["project"], console=c)
    assert rc == 2
    assert any("尚未实现" in line for line in c.stdout)
