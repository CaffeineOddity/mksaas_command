"""tests.test_masking — 脱敏测试。"""

from mksaas.masking import mask


def test_mask_empty():
    assert mask("") == "<empty>"


def test_mask_short_value_shown_but_truncated():
    # 短值（<=8）只露首尾各一部分，避免完整泄露
    out = mask("abcd")
    assert out != "abcd"
    assert "abcd" not in out.replace("*", "")


def test_mask_long_value_head_tail():
    out = mask("abcdefghij")
    assert out.startswith("abcd")
    assert out.endswith("ghij")
    assert "efgh" not in out  # 中间不泄露


def test_mask_does_not_leak_full():
    secret = "supersecrettoken1234567890"
    out = mask(secret)
    assert secret not in out
