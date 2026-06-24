"""mksaas.masking — 密钥/连接串/token 摘要脱敏。

REQUIREMENTS §3.4/§9.1：终端输出对敏感内容做摘要，避免直接打印完整值。
纯函数，无副作用。
"""

from __future__ import annotations

_SHORT_THRESHOLD = 8  # 短于等于此长度即视为短值


def mask(value: str) -> str:
    """对敏感值做摘要：空→<empty>；短值用星号遮挡；长值露首4尾4。"""
    if value is None or value == "":
        return "<empty>"
    if len(value) <= _SHORT_THRESHOLD:
        # 短值不露完整内容，仅以星号占位并给长度提示
        return "*" * len(value)
    return f"{value[:4]}…{value[-4:]}"
