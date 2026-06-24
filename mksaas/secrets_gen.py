"""mksaas.secrets_gen — 安全随机数生成。

REQUIREMENTS §9.2：BETTER_AUTH_SECRET 必须用 Python 安全随机数，不使用弱随机，
默认长度满足现代安全要求。仅用 secrets 模块。
"""

from __future__ import annotations

import secrets

# token_urlsafe(48) 产生约 64 字符的 URL 安全串，满足现代应用安全要求
_SECRET_BYTES = 48


def gen_better_auth_secret() -> str:
    """生成 BETTER_AUTH_SECRET 安全密钥。"""
    return secrets.token_urlsafe(_SECRET_BYTES)
