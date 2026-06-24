"""tests.test_secrets_gen — 安全密钥生成测试。"""

from mksaas.secrets_gen import gen_better_auth_secret


def test_length_sufficient():
    s = gen_better_auth_secret()
    assert len(s) >= 32


def test_randomness():
    a = gen_better_auth_secret()
    b = gen_better_auth_secret()
    assert a != b


def test_urlsafe_characters():
    s = gen_better_auth_secret()
    # token_urlsafe 仅含 A-Za-z0-9-_
    assert all(c.isalnum() or c in "-_" for c in s)
