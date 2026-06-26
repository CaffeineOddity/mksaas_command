"""mksaas.console — 终端 I/O 缝。

把所有 print/input/getpass/选择/采集收敛到 Console 接口，便于在测试中注入
FakeConsole 而非驱动真实 PTY。TerminalConsole 用 questionary 实现交互式
text/select/confirm；FakeConsole 用预置队列驱动，断言输出与模拟输入。
"""

from __future__ import annotations

import getpass
import sys
from typing import List, Optional, Sequence

# ANSI：蓝色加粗。header 前留一空行，醒目分组边界。
_HEADER_STYLE = "\033[1;34m"
_RESET = "\033[0m"


def _supports_color() -> bool:
    """是否向终端输出彩色（非 TTY 时不加转义码，避免污染管道/日志）。"""
    return sys.stdout.isatty()


def _is_interactive() -> bool:
    """是否处于可交互终端（questionary 需要 TTY）。"""
    return sys.stdin.isatty() and sys.stdout.isatty()


class Console:
    """终端 I/O 抽象基类。子类实现具体交互。"""

    def print(self, message: str = "") -> None:  # noqa: A003 - 接口名刻意取 print
        """输出一行到终端。"""
        raise NotImplementedError

    def header(self, text: str) -> None:
        """输出一个章节标题：前留空行，蓝色加粗（非 TTY 时退化为纯文本）。"""
        raise NotImplementedError

    def input(self, prompt: str = "", default: str = "") -> str:  # noqa: A003
        """读取用户一行输入（可预填默认值，留空返回 default）。"""
        raise NotImplementedError

    def getpass(self, prompt: str = "", default: str = "") -> str:
        """读取敏感输入（隐藏回显，留空返回 default）。"""
        raise NotImplementedError

    def confirm(self, prompt: str, default: bool = False) -> bool:
        """是/否确认，返回布尔。"""
        raise NotImplementedError

    def choose(self, prompt: str, options: Sequence[str], default: int = 1) -> int:
        """数字/箭头菜单：返回 1-based 选项序号。"""
        raise NotImplementedError


class TerminalConsole(Console):
    """默认终端实现：questionary 驱动交互，非 TTY 回退到标准库。"""

    def print(self, message: str = "") -> None:
        print(message)

    def header(self, text: str) -> None:
        print("")  # 前留空行
        line = f"=== {text} ==="
        if _supports_color():
            print(f"{_HEADER_STYLE}{line}{_RESET}")
        else:
            print(line)

    def input(self, prompt: str = "", default: str = "") -> str:
        """questionary.text 预填默认值；非 TTY 回退 input()。"""
        if not _is_interactive():
            try:
                raw = input(f"{prompt} [{default}] ").strip() if prompt else input().strip()
            except EOFError:
                return default
            return raw if raw else default
        import questionary
        result = questionary.text(prompt, default=default).ask()
        if result is None:  # Ctrl-C / Ctrl-D
            raise KeyboardInterrupt
        return result

    def getpass(self, prompt: str = "", default: str = "") -> str:
        """敏感字段：questionary.text 隐藏输入（is_password=True）。"""
        if not _is_interactive():
            try:
                raw = getpass.getpass(f"{prompt} [{default}] ")
            except EOFError:
                return default
            return raw if raw else default
        import questionary
        result = questionary.text(prompt, default=default, is_password=True).ask()
        if result is None:
            raise KeyboardInterrupt
        return result

    def confirm(self, prompt: str, default: bool = False) -> bool:
        if not _is_interactive():
            hint = "[Y/n]" if default else "[y/N]"
            raw = input(f"{prompt} {hint} ").strip().lower()
            if raw == "":
                return default
            return raw in ("y", "yes")
        import questionary
        return bool(questionary.confirm(prompt, default=default).ask())

    def choose(self, prompt: str, options: Sequence[str], default: int = 1) -> int:
        """questionary.select 箭头选择；非 TTY 回退数字输入。"""
        if not _is_interactive():
            menu = self._format_menu(options)
            head = f"\n{prompt}\n" if prompt else "\n"
            try:
                raw = input(f"{head}{menu}\n选择> ").strip()
            except EOFError:
                return default
            if raw == "":
                return default
            try:
                idx = int(raw)
            except ValueError:
                return default
            return idx if 1 <= idx <= len(options) else default
        import questionary
        default_choice = options[default - 1] if 1 <= default <= len(options) else options[0]
        result = questionary.select(prompt or "请选择", choices=list(options), default=default_choice).ask()
        if result is None:
            raise KeyboardInterrupt
        return options.index(result) + 1

    @staticmethod
    def _format_menu(options: Sequence[str]) -> str:
        """非 TTY 回退时渲染数字菜单。"""
        return "  ".join(f"{i}: {label}" for i, label in enumerate(options, start=1))


class FakeConsole(Console):
    """测试用桩：预置响应队列并记录输出。

    header 与 print 记录纯文本（不含 ANSI 转义码），断言免处理颜色。
    input/getpass/confirm/choose 从队列取值；input/getpass 留空返回 default。
    """

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

    def header(self, text: str) -> None:
        self.stdout.append("")  # 与 TerminalConsole 一致：前留空行
        self.stdout.append(f"=== {text} ===")

    def input(self, prompt: str = "", default: str = "") -> str:
        if not self._inputs:
            raise IndexError(f"FakeConsole input 队列为空：{prompt!r}")
        raw = self._inputs.pop(0)
        return raw if raw != "" else default

    def getpass(self, prompt: str = "", default: str = "") -> str:
        if not self._secrets:
            raise IndexError(f"FakeConsole secrets 队列为空：{prompt!r}")
        raw = self._secrets.pop(0)
        return raw if raw != "" else default

    def confirm(self, prompt: str, default: bool = False) -> bool:
        if not self._inputs:
            raise IndexError(f"FakeConsole input 队列为空：{prompt!r}")
        raw = self._inputs.pop(0).strip().lower()
        if raw == "":
            return default
        return raw in ("y", "yes")

    def choose(self, prompt: str, options: Sequence[str], default: int = 1) -> int:
        if not self._inputs:
            raise IndexError(f"FakeConsole input 队列为空：{prompt!r}")
        raw = self._inputs.pop(0).strip()
        if raw == "":
            return default
        try:
            idx = int(raw)
        except ValueError:
            return default
        return idx if 1 <= idx <= len(options) else default
