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
    for m in ("print", "input", "getpass", "confirm"):
        assert hasattr(t, m), f"TerminalConsole 缺方法 {m}"
