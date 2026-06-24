"""mksaas.repo_url — 仓库 URL 清洗。

REQUIREMENTS §9.3：状态文件只存干净 URL，不得含 user:token@ 鉴权段；
误输入时剥离并提示。纯函数。
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

# 形如 user:pass@ 的鉴权段
_AUTH_RE = re.compile(r"^[^/@:]+:[^/@:]+@")


def clean_repo_url(url: str) -> tuple:
    """清洗 repo_url，返回 (干净 url, 是否剥离过鉴权段)。

    非法 URL 抛 ValueError（中文）。SSH 形式（git@host:path）原样返回。
    """
    if not url or not isinstance(url, str):
        raise ValueError("仓库地址为空")
    url = url.strip()

    # SSH 形式：git@github.com:o/r.git —— 无 https 鉴权段，原样返回
    if url.startswith("git@"):
        return url, False

    # 解析 https/http URL
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        raise ValueError(f"仓库地址格式错误：{url}")

    stripped = False
    netloc = parts.netloc
    if "@" in netloc:
        # 形如 user:token@host
        at_idx = netloc.rfind("@")
        userinfo = netloc[:at_idx]
        host = netloc[at_idx + 1:]
        if userinfo:
            stripped = True
            netloc = host

    cleaned = urlunsplit((parts.scheme, netloc, parts.path, "", ""))
    return cleaned, stripped
