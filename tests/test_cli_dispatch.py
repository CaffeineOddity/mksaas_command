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
    # upgrade/uninstall 尚未实现（F11），验证分发返回未实现码
    c = FakeConsole()
    rc = main(["upgrade", "--local"], console=c)
    assert rc == 2
    assert any("尚未实现" in line for line in c.stdout)
