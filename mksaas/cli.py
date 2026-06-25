"""mksaas.cli — argparse 主入口与子命令分发。

本模块负责构建顶层 CLI 解析器并把命令分发到各 commands/* 子模块。
所有终端 I/O 经 Console 缝，便于测试注入。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from mksaas import paths, version
from mksaas.console import Console, TerminalConsole
from mksaas.groups import groups_in_order, group_snake_to_kebab

_ENV_GROUP_SUMMARIES = {
    "core": "基础站点 URL 与回调地址",
    "database": "数据库连接",
    "better_auth": "认证密钥与鉴权核心配置",
    "github_oauth": "GitHub 登录配置",
    "google_oauth": "Google 登录配置",
    "email_newsletter": "邮件与订阅配置",
    "storage": "对象存储配置",
    "payment": "支付配置",
    "configurations": "通用业务开关与运行配置",
    "analytics": "统计分析配置",
    "notification": "通知渠道配置",
    "affiliate": "联盟分销配置",
    "captcha": "人机验证配置",
    "crisp": "Crisp 在线客服配置",
    "cron_jobs": "定时任务鉴权配置",
    "ai": "AI 模型与密钥配置",
    "firecrawl": "Firecrawl 抓取配置",
}


class HelpFormatter(argparse.RawTextHelpFormatter):
    """保持帮助文案的换行与缩进，输出更接近命令手册。"""

    def __init__(self, prog: str) -> None:
        """固定帮助列位置，避免短说明被意外换到下一行。"""
        super().__init__(prog, max_help_position=28)

    def _format_action(self, action: argparse.Action) -> str:
        """对子命令列表使用稳定的一行式排版。"""
        if isinstance(action, argparse._SubParsersAction):
            parts = [f"{self._current_indent * ' '}{self._format_action_invocation(action)}\n"]
            subactions = action._get_subactions()
            if not subactions:
                return "".join(parts)

            self._indent()
            width = max(len(self._format_action_invocation(subaction)) for subaction in subactions)
            for subaction in subactions:
                command = self._format_action_invocation(subaction)
                help_text = self._expand_help(subaction) if subaction.help else ""
                parts.append(
                    f"{self._current_indent * ' '}{command.ljust(width)}  {help_text}\n"
                )
            self._dedent()
            return "".join(parts)
        return super()._format_action(action)


def _env_groups_help_text() -> str:
    """生成 env 子命令 help 中展示的可用分组列表。"""
    group_ids = groups_in_order()
    width = max(len(group_snake_to_kebab(group_id)) for group_id in group_ids)
    lines = []
    for group_id in group_ids:
        kebab = group_snake_to_kebab(group_id)
        summary = _ENV_GROUP_SUMMARIES[group_id]
        lines.append(f"  {kebab.ljust(width)}  {summary}")
    return "\n".join(lines)


def _display_version() -> str:
    """返回 CLI 当前应显示的版本字符串。"""
    meta = paths.install_metadata()
    installed_from = meta.get("installed_from")
    if isinstance(installed_from, str) and installed_from and installed_from != "source":
        return installed_from

    repo_root = paths.repo_root()
    if repo_root is not None:
        config_file = repo_root / "build.config.json"
        if config_file.is_file():
            try:
                version_str, build_num = version.read_version(config_file)
            except version.VersionError:
                pass
            else:
                return version.version_string(version_str, build_num, release=False)

    source_root = Path(__file__).resolve().parent.parent
    config_file = source_root / "build.config.json"
    if config_file.is_file():
        try:
            version_str, build_num = version.read_version(config_file)
        except version.VersionError:
            pass
        else:
            return version.version_string(version_str, build_num, release=False)

    if isinstance(installed_from, str) and installed_from:
        return installed_from
    return "unknown"


def build_parser() -> argparse.ArgumentParser:
    """构造顶层 argparse 解析器并注册全部子命令。"""
    parser = argparse.ArgumentParser(
        prog="mksaas",
        description="MkSaaS 配置编排 CLI",
        epilog=(
            "常用命令:\n"
            "  mksaas init\n"
            "  mksaas env github-oauth --profile prod\n"
            "  mksaas apply\n"
            "  mksaas upgrade --local\n"
            "\n"
            "使用 'mksaas <command> --help' 查看单个命令说明。"
        ),
        formatter_class=HelpFormatter,
    )
    parser.add_argument("--version", action="store_true", help="显示版本号")
    sub = parser.add_subparsers(dest="command", title="命令", metavar="<command>")

    sub.add_parser(
        "init",
        help="全流程编排器",
        description="从项目初始化开始，串行引导整个配置流程。",
        formatter_class=HelpFormatter,
    )
    sub.add_parser(
        "project",
        help="采集项目与仓库信息并就位本地目录",
        description="采集项目与仓库信息，并准备本地工作目录。",
        formatter_class=HelpFormatter,
    )

    env = sub.add_parser(
        "env",
        help="采集某一环境分组",
        usage="mksaas env <group> [--profile <test | prod>] [-h]",
        description=(
            "采集并更新单个环境分组。"
        ),
        epilog=(
            "示例:\n"
            "  mksaas env core\n"
            "  mksaas env github-oauth --profile prod"
        ),
        formatter_class=HelpFormatter,
    )
    env.add_argument(
        "group",
        nargs="?",
        metavar="group",
        help=(
            "环境分组名称:\n"
            f"{_env_groups_help_text()}"
        ),
    )
    env.add_argument(
        "--profile",
        choices=["test", "prod"],
        default=None,
        help="目标 profile（test 或 prod）",
    )

    sub.add_parser(
        "apply",
        help="统一执行落地",
        description="根据当前状态统一执行落地操作。",
        formatter_class=HelpFormatter,
    )

    upgrade = sub.add_parser(
        "upgrade",
        help="从本地构建产物升级",
        description="从本地 .build/dist 构建产物升级当前安装。",
        formatter_class=HelpFormatter,
    )
    upgrade.add_argument("--local", action="store_true", help="从本地产物升级")

    sub.add_parser(
        "uninstall",
        help="卸载本地安装",
        description="卸载本地安装的 mksaas 命令。",
        formatter_class=HelpFormatter,
    )
    return parser


def main(argv: Optional[List[str]] = None, console: Optional[Console] = None) -> int:
    """解析 argv 并分发到子命令，返回退出码。"""
    console = console or TerminalConsole()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        console.print(f"mksaas {_display_version()}")
        return 0

    if not args.command:
        parser.print_help()
        return 1

    # 各子命令实现于 commands 包；未注册命令由 argparse 报错。
    from mksaas import commands as cmd

    dispatch = {
        "init": cmd.run_init,
        "project": cmd.run_project,
        "env": cmd.run_env,
        "apply": cmd.run_apply,
        "upgrade": cmd.run_upgrade,
        "uninstall": cmd.run_uninstall,
    }
    handler = dispatch.get(args.command)
    if handler is None:
        console.print(f"命令 { args.command } 尚未实现")
        return 2
    return handler(args, console)


if __name__ == "__main__":
    sys.exit(main())
