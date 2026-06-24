#!/usr/bin/env bash
# install.sh — 本地目录 + 符号链接安装 mksaas。
# 真相来源：docs/build_install_upgrade_uninstall.md §5/§6
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.mksaas-cli"
EXEC="$INSTALL_DIR/mksaas"

usage() {
  cat <<'EOF' >&2
用法: install.sh [--version <版本字符串>] [-h|--help]

把 mksaas 安装为本地可调用命令（本地目录 + 符号链接）。

安装行为:
  - 安装目录: ~/.mksaas-cli（存放可执行文件与版本信息）
  - 符号链接: 优先 /usr/local/bin，不可写时回退 ~/.local/bin
  - 安装来源: 默认安装 dist/ 下最新版本产物；否则安装源码入口（开发态）
  - 已存在安装时按升级语义覆盖旧版

选项:
  --version <版本字符串>  强制安装 dist/ 下指定版本子目录的产物
                          （如 0.1.0-dev1、0.1.0），不再取最新；
                          该版本不存在时报错退出
  -h, --help              显示本帮助

安装后:
  - 确认 PATH 包含符号链接所在目录
  - 若回退到 ~/.local/bin 且不在 PATH，请手动加入 shell 配置
  - 不自动修改 shell 配置文件

示例:
  ./install.sh                          # 安装最新产物（或源码入口）
  ./install.sh --version 0.1.0-dev1     # 强制安装指定 debug 版本
  ./install.sh --version 0.1.0          # 强制安装指定 release 版本
  build.sh && ./install.sh              # 先构建产物再安装

升级/卸载也可通过已安装的命令完成:
  mksaas upgrade --local   # 从本地构建产物升级
  mksaas uninstall         # 卸载

完整规则见 docs/build_install_upgrade_uninstall.md §5/§6
EOF
}

WANT_VERSION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --version)
      if [[ $# -lt 2 ]]; then
        echo "错误: --version 需要一个版本字符串参数" >&2
        exit 1
      fi
      WANT_VERSION="$2"; shift 2 ;;
    *) echo "未知参数: $1" >&2; usage; exit 1 ;;
  esac
done

# 来源判定：dist 下最新版本产物优先；否则安装源码入口（开发态）
pick_source() {
  # 指定版本：精确匹配 dist/<WANT_VERSION>/mksaas
  if [[ -n "$WANT_VERSION" ]]; then
    local target="$REPO_ROOT/dist/$WANT_VERSION/mksaas"
    if [[ -f "$target" ]]; then
      echo "$target"
      return 0
    fi
    echo "错误: 指定版本产物不存在：dist/$WANT_VERSION/mksaas" >&2
    echo "可用版本：" >&2
    if [[ -d "$REPO_ROOT/dist" ]]; then
      for d in "$REPO_ROOT/dist"/*/; do
        [[ -f "${d}mksaas" ]] && echo "  $(basename "$d")" >&2
      done
    fi
    exit 1
  fi

  # 默认：取最新版本
  local latest
  latest="$(python3 - "$REPO_ROOT" <<'PY'
import sys, json
from pathlib import Path
root = Path(sys.argv[1])
dist = root / "dist"
if dist.is_dir():
    subs = [p for p in dist.iterdir() if p.is_dir() and (p / "mksaas").is_file()]
    if subs:
        def key(p):
            s = p.name
            import re
            m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-dev(\d+))?$", s)
            if not m: return (0,0,0,1,0)
            major,minor,patch = map(int, m.group(1,2,3))
            dev = int(m.group(4)) if m.group(4) else None
            return (major,minor,patch, 1 if dev is None else 0, dev or 0)
        subs.sort(key=key)
        print(subs[-1] / "mksaas")
        sys.exit(0)
print("")
PY
)"
  if [[ -n "$latest" ]]; then
    echo "$latest"
  else
    echo "source"
  fi
}

SOURCE="$(pick_source)"

mkdir -p "$INSTALL_DIR"
if [[ "$SOURCE" == "source" ]]; then
  # 开发态安装：写一个调用源码入口的包装脚本
  cat > "$EXEC" <<EOF
#!/usr/bin/env bash
exec python3 "$REPO_ROOT/mksaas/__main__.py" "\$@"
EOF
  chmod +x "$EXEC"
else
  cp "$SOURCE" "$EXEC"
  chmod +x "$EXEC"
fi

# 符号链接 PATH 优先级：/usr/local/bin 优先，不可写回退 ~/.local/bin
LINK_DIR=""
if [[ -w "/usr/local/bin" ]]; then
  LINK_DIR="/usr/local/bin"
else
  LINK_DIR="${HOME}/.local/bin"
  mkdir -p "$LINK_DIR"
fi
ln -sf "$EXEC" "$LINK_DIR/mksaas"

echo "已安装：$EXEC"
echo "符号链接：$LINK_DIR/mksaas"
if [[ "$LINK_DIR" == "${HOME}/.local/bin" ]]; then
  case ":${PATH}:" in
    *":${HOME}/.local/bin:"*) ;;
    *) echo "提示：${HOME}/.local/bin 不在 PATH，请将其加入 shell 配置" ;;
  esac
fi
echo "请确认 PATH 包含 $LINK_DIR"
