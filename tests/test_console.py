"""tests.test_console — Console 缝测试。"""

from mksaas.console import FakeConsole, TerminalConsole


def test_fake_console_records_print():
    c = FakeConsole()
    c.print("hello")
    assert "hello" in c.stdout


def test_fake_console_input_from_queue():
    c = FakeConsole(inputs=["a", "b"])
    assert c.input("q?") == "a"
    assert c.input("q?") == "b"


def test_fake_console_input_empty_raises():
    c = FakeConsole()
    try:
        c.input("q?")
    except IndexError:
        return
    raise AssertionError("应抛 IndexError")


def test_fake_console_getpass_from_queue():
    c = FakeConsole(secrets=["s3cr3t"])
    assert c.getpass("secret?") == "s3cr3t"


def test_fake_console_confirm_yes():
    c = FakeConsole(inputs=["y"])
    assert c.confirm("ok?") is True


def test_fake_console_confirm_yes_word():
    c = FakeConsole(inputs=["yes"])
    assert c.confirm("ok?") is True


def test_fake_console_confirm_no():
    c = FakeConsole(inputs=["n"])
    assert c.confirm("ok?") is False


def test_fake_console_confirm_empty_uses_default():
    c = FakeConsole(inputs=[""])
    assert c.confirm("ok?", default=True) is True
    c2 = FakeConsole(inputs=[""])
    assert c2.confirm("ok?", default=False) is False


def test_terminal_console_has_same_methods():
    t = TerminalConsole()
    for m in ("print", "header", "input", "getpass", "confirm", "choose"):
        assert hasattr(t, m), f"TerminalConsole 缺方法 {m}"


def test_fake_console_header_records_blank_line_then_text():
    c = FakeConsole()
    c.header("分组 core")
    assert c.stdout == ["", "=== 分组 core ==="]


def test_fake_console_choose_returns_index():
    c = FakeConsole(inputs=["2"])
    assert c.choose("选", ["处理", "跳过", "结束"]) == 2


def test_fake_console_choose_empty_uses_default():
    c = FakeConsole(inputs=[""])
    assert c.choose("选", ["处理", "跳过"], default=2) == 2


def test_fake_console_choose_invalid_uses_default():
    c = FakeConsole(inputs=["x", "9", "0"])
    assert c.choose("选", ["处理", "结束"], default=1) == 1
    assert c.choose("选", ["处理", "结束"], default=1) == 1
    assert c.choose("选", ["处理", "结束"], default=2) == 2
