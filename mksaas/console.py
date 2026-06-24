"""mksaas.console — 终端 I/O 缝。

把所有 print/input/getpass 收敛到 Console 接口，便于在测试中注入 FakeConsole
而非驱动真实 PTY。TerminalConsole 是默认实现；FakeConsole 用于断言输出与模拟输入。
"""

from __future__ import annotations

import getpass
from typing import List, Optional


class Console:
    """终端 I/O 抽象基类。子类实现具体交互。"""

    def print(self, message: str = "") -> None:  # noqa: A003 - 接口名刻意取 print
        """输出一行到终端。"""
        raise NotImplementedError

    def input(self, prompt: str = "") -> str:  # noqa: A003
        """读取用户一行输入。"""
        raise NotImplementedError

    def getpass(self, prompt: str = "") -> str:
        """读取敏感输入（隐藏回显）。"""
        raise NotImplementedError

    def confirm(self, prompt: str, default: bool = False) -> bool:
        """是/否确认，返回布尔。"""
        raise NotImplementedError


class TerminalConsole(Console):
    """默认终端实现，直接调用标准库。"""

    def print(self, message: str = "") -> None:
        print(message)

    def input(self, prompt: str = "") -> str:
        return input(prompt)

    def getpass(self, prompt: str = "") -> str:
        return getpass.getpass(prompt)

    def confirm(self, prompt: str, default: bool = False) -> bool:
        hint = "[Y/n]" if default else "[y/N]"
        raw = self.input(f"{prompt} {hint} ").strip().lower()
        if raw == "":
            return default
        return raw in ("y", "yes")


class FakeConsole(Console):
    """测试用桩：预置响应队列并记录输出。"""

    def __init__(
        self,
        inputs: Optional[List[str]] = None,
        secrets: Optional[List[str]] = None,
    ) -> None:
        self.stdout: List[str] = []
        self._inputs: List[str] = list(inputs or [])
        self._secrets: List[str] = list(secrets or [])

    def print(self, message: str = "") -> None:
        self.stdout.append(message)

    def input(self, prompt: str = "") -> str:
        if not self._inputs:
            raise IndexError(f"FakeConsole input 队列为空：{prompt!r}")
        return self._inputs.pop(0)

    def getpass(self, prompt: str = "") -> str:
        if not self._secrets:
            raise IndexError(f"FakeConsole secrets 队列为空：{prompt!r}")
        return self._secrets.pop(0)

    def confirm(self, prompt: str, default: bool = False) -> bool:
        raw = self.input(f"{prompt} ").strip().lower()
        if raw == "":
            return default
        return raw in ("y", "yes")
