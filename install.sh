#!/usr/bin/env bash
# install.sh — 本地目录 + 符号链接安装 mksaas。
# 真相来源：docs/build_install_upgrade_uninstall.md §5/§6
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.mksaas-cli"
EXEC="$INSTALL_DIR/mksaas"
CURRENT_PATH="$INSTALL_DIR/current"
BUILD_DIST_DIR="$REPO_ROOT/.build/dist"

usage() {
  cat <<'EOF' >&2
用法: install.sh [--version <版本字符串>] [-h|--help]

把 mksaas 安装为本地可调用命令（本地目录 + 符号链接）。

安装行为:
  - 安装目录: ~/.mksaas-cli（存放可执行文件与版本信息）
  - 符号链接: 优先 /usr/local/bin，不可写时回退 ~/.local/bin
  - 安装来源: 默认安装源码入口（开发态）
  - 指定版本: 仅在传入 --version 时安装 .build/dist/ 下的发布产物
  - 已存在安装时按升级语义覆盖旧版

选项:
  --version <版本字符串>  安装 .build/dist/ 下指定版本子目录的产物
                          （如 0.1.0-dev1、0.1.0），支持 onedir / onefile；
                          该版本不存在时报错退出
  -h, --help              显示本帮助

安装后:
  - 确认 PATH 包含符号链接所在目录
  - 若回退到 ~/.local/bin 且不在 PATH，请手动加入 shell 配置
  - 不自动修改 shell 配置文件

示例:
  ./install.sh                          # 安装源码入口（开发态）
  ./install.sh --version 0.1.0-dev1     # 安装指定 debug 版本产物
  ./install.sh --version 0.1.0          # 安装指定 release 版本产物
  ./build.sh --release && ./install.sh --version 0.1.0
                                        # 先构建 release 再安装

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

# 解析安装来源：默认源码入口；指定版本时识别 onedir / onefile 产物。
pick_source() {
  python3 - "$BUILD_DIST_DIR" "$WANT_VERSION" <<'PY'
import sys
from pathlib import Path
dist = Path(sys.argv[1])
want = sys.argv[2]

if not want:
    print("source\t\t")
    raise SystemExit(0)

product = dist / want / "mksaas"
if product.is_dir() and (product / "mksaas").is_file():
    print(f"onedir\t{product}\t{want}")
    raise SystemExit(0)
if product.is_file():
    print(f"onefile\t{product}\t{want}")
    raise SystemExit(0)

print(f"错误: 指定版本产物不存在：.build/dist/{want}/mksaas", file=sys.stderr)
print("可用版本：", file=sys.stderr)
if dist.is_dir():
    for sub in sorted(p for p in dist.iterdir() if p.is_dir()):
        container = sub / "mksaas"
        if container.is_file() or (container.is_dir() and (container / "mksaas").is_file()):
            print(f"  {sub.name}", file=sys.stderr)
raise SystemExit(1)
PY
}

write_exec_wrapper() {
  local target_cmd="$1"
  local tmp_exec="$EXEC.tmp"
  cat > "$tmp_exec" <<EOF
#!/usr/bin/env bash
exec "$target_cmd" "\$@"
EOF
  chmod +x "$tmp_exec"
  mv "$tmp_exec" "$EXEC"
}

write_source_wrapper() {
  local tmp_exec="$EXEC.tmp"
  cat > "$tmp_exec" <<EOF
#!/usr/bin/env bash
exec python3 "$REPO_ROOT/mksaas/__main__.py" "\$@"
EOF
  chmod +x "$tmp_exec"
  mv "$tmp_exec" "$EXEC"
}

stage_product() {
  local source_kind="$1"
  local source_path="$2"
  local stage_dir="$3"

  rm -rf "$stage_dir"
  mkdir -p "$stage_dir"
  case "$source_kind" in
    onefile)
      cp "$source_path" "$stage_dir/mksaas"
      chmod +x "$stage_dir/mksaas"
      ;;
    onedir)
      cp -R "$source_path" "$stage_dir/mksaas"
      chmod +x "$stage_dir/mksaas/mksaas"
      ;;
    *)
      echo "错误: 不支持的产物类型：$source_kind" >&2
      exit 1
      ;;
  esac
}

replace_current() {
  local stage_dir="$1"
  local backup_dir="${CURRENT_PATH}.bak"

  rm -rf "$backup_dir"
  if [[ -e "$CURRENT_PATH" ]]; then
    mv "$CURRENT_PATH" "$backup_dir"
  fi
  if mv "$stage_dir" "$CURRENT_PATH"; then
    rm -rf "$backup_dir"
    return 0
  fi
  rm -rf "$CURRENT_PATH"
  if [[ -e "$backup_dir" ]]; then
    mv "$backup_dir" "$CURRENT_PATH"
  fi
  return 1
}

IFS=$'\t' read -r SOURCE_KIND SOURCE_PATH INSTALLED_FROM <<<"$(pick_source)"
INSTALL_MODE="source"

mkdir -p "$INSTALL_DIR"

if [[ "$SOURCE_KIND" == "source" ]]; then
  write_source_wrapper
  rm -rf "$CURRENT_PATH" "${CURRENT_PATH}.bak" "${CURRENT_PATH}.tmp"
  INSTALLED_FROM="source"
else
  stage_product "$SOURCE_KIND" "$SOURCE_PATH" "${CURRENT_PATH}.tmp"
  replace_current "${CURRENT_PATH}.tmp" || {
    echo "错误: 替换安装目录中的发布产物失败" >&2
    exit 1
  }
  if [[ "$SOURCE_KIND" == "onedir" ]]; then
    write_exec_wrapper "$CURRENT_PATH/mksaas/mksaas"
  else
    write_exec_wrapper "$CURRENT_PATH/mksaas"
  fi
  INSTALL_MODE="$SOURCE_KIND"
fi

python3 - "$INSTALL_DIR/VERSION.installed" "$INSTALLED_FROM" "$REPO_ROOT" "$BUILD_DIST_DIR" "$INSTALL_MODE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = {
    "installed_from": sys.argv[2],
    "repo_root": sys.argv[3],
    "build_dist_dir": sys.argv[4],
    "install_mode": sys.argv[5],
}
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY

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
echo "安装模式：$INSTALL_MODE"
echo "符号链接：$LINK_DIR/mksaas"
if [[ "$LINK_DIR" == "${HOME}/.local/bin" ]]; then
  case ":${PATH}:" in
    *":${HOME}/.local/bin:"*) ;;
    *) echo "提示：${HOME}/.local/bin 不在 PATH，请将其加入 shell 配置" ;;
  esac
fi
echo "请确认 PATH 包含 $LINK_DIR"
