"""mksaas.cli — argparse 主入口与子命令分发。

本模块负责构建顶层 CLI 解析器并把命令分发到各 commands/* 子模块。
所有终端 I/O 经 Console 缝，便于测试注入。
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from mksaas import __version__
from mksaas.console import Console, TerminalConsole
from mksaas.groups import GROUP_SUMMARIES, groups_in_order, group_snake_to_kebab


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
    """生成 env 子命令 help 中展示的可用分组列表（含必填标记）。

    必填标记从 env-schema.yaml 读取：组内任一变量 required 即标 [必填]。
    """
    from mksaas.groups import is_required_group
    from mksaas.schema import load_schema

    schema_groups = {g["id"]: g for g in load_schema()}
    group_ids = groups_in_order()
    width = max(len(group_snake_to_kebab(group_id)) for group_id in group_ids)
    lines = []
    for group_id in group_ids:
        kebab = group_snake_to_kebab(group_id)
        summary = GROUP_SUMMARIES[group_id]
        required_tag = "[必填]" if is_required_group(group_id) else "[可选]"
        # 统计变量数与必填变量数
        variables = schema_groups.get(group_id, {}).get("variables", [])
        total = len(variables)
        req_n = sum(1 for v in variables if v.get("required"))
        var_info = f"{total} 变量" + (f"，必填 {req_n}" if req_n else "")
        lines.append(f"  {kebab.ljust(width)}  {required_tag} {summary}（{var_info}）")
    return "\n".join(lines)


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
            "  mksaas upgrade --local .\n"
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

    sub.add_parser(
        "help",
        help="显示帮助信息",
        description="显示本 CLI 的帮助信息。",
        formatter_class=HelpFormatter,
    )
    sub.add_parser(
        "version",
        help="打印当前版本号",
        description="打印当前版本号。",
        formatter_class=HelpFormatter,
    )

    upgrade = sub.add_parser(
        "upgrade",
        help="升级本 CLI（默认从 PyPI，--local 用本地构建产物）",
        description="升级本 CLI：默认从 PyPI 拉取 release，或用 --local 从本地构建产物安装。",
        formatter_class=HelpFormatter,
    )
    upgrade.add_argument("--version", default=None, help="升级到指定版本")
    upgrade.add_argument(
        "--local",
        default=None,
        help="从本地项目的构建产物升级（指向项目根路径）",
    )

    sub.add_parser(
        "uninstall",
        help="卸载本 CLI",
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
        console.print(f"mksaas {__version__}")
        return 0

    if not args.command:
        parser.print_help()
        return 1

    # 各子命令实现于 commands 包；未注册命令由 argparse 报错。
    from mksaas import commands as cmd

    if args.command == "help":
        return cmd.run_help(parser)

    # 业务命令采用 (args, console) 签名
    business = {
        "init": cmd.run_init,
        "project": cmd.run_project,
        "env": cmd.run_env,
        "apply": cmd.run_apply,
    }
    handler = business.get(args.command)
    if handler is not None:
        return handler(args, console)

    # 交付外壳命令采用 (args) 签名
    shell = {
        "version": cmd.run_version,
        "upgrade": cmd.run_upgrade,
        "uninstall": cmd.run_uninstall,
    }
    handler = shell.get(args.command)
    if handler is not None:
        return handler(args)

    console.print(f"命令 { args.command } 尚未实现")
    return 2


if __name__ == "__main__":
    sys.exit(main())
