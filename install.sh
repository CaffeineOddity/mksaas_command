#!/usr/bin/env bash
# install.sh — 本地目录 + 符号链接安装当前应用。
# 真相来源：docs/build_install_upgrade_uninstall.md §5/§6
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$REPO_ROOT/build.config.json"

# read_install_config_for_help: 读取配置；缺失时回退到保守默认值，便于 --help 展示。
read_install_config_for_help() {
  python3 - "$CONFIG_FILE" "$REPO_ROOT" <<'PY'
import json, sys
from pathlib import Path

config = Path(sys.argv[1])
repo_root = Path(sys.argv[2])
defaults = {
    "app_name": repo_root.name,
    "entry": "main.py",
    "build_root": ".build",
}
if config.is_file():
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    if isinstance(data, dict):
        defaults.update({
            "app_name": data.get("app_name", defaults["app_name"]),
            "entry": data.get("entry", defaults["entry"]),
            "build_root": data.get("build_root", defaults["build_root"]),
        })
print("\t".join([defaults["app_name"], defaults["entry"], defaults["build_root"]]))
PY
}

# read_install_config: 严格读取 build.config.json，供安装流程使用。
read_install_config() {
  python3 - "$CONFIG_FILE" <<'PY'
import json, sys

path = sys.argv[1]
data = json.load(open(path, encoding="utf-8"))
print("\t".join([
    data["app_name"],
    data["entry"],
    data.get("build_root", ".build"),
]))
PY
}

usage() {
  local app_name entry_rel build_root_rel install_dir
  IFS=$'\t' read -r app_name entry_rel build_root_rel <<<"$(read_install_config_for_help)"
  install_dir="${HOME}/.${app_name}-cli"
  cat <<EOF >&2
用法: install.sh [--version <版本字符串>] [-h|--help]

把 ${app_name} 安装为本地可调用命令。

选项:
  --version <版本字符串>  安装 ${build_root_rel}/dist/ 下指定版本的发布产物
                          该版本不存在时报错退出
  -h, --help              显示本帮助

说明:
  - 默认安装源码入口，适合开发态
  - 传 --version 时安装指定发布产物
  - 构建配置: build.config.json
  - 安装目录: ${install_dir}
  - 符号链接: 优先 /usr/local/bin，不可写时回退 ~/.local/bin

示例:
  ./install.sh
  ./install.sh --version 0.1.0-dev1
  ./install.sh --version 0.1.0

升级/卸载也可通过已安装的命令完成:
  ${app_name} upgrade --local   # 从本地构建产物升级
  ${app_name} uninstall         # 卸载

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

IFS=$'\t' read -r APP_NAME ENTRY_REL BUILD_ROOT_REL <<<"$(read_install_config)"
ENTRY_PATH="$REPO_ROOT/$ENTRY_REL"
INSTALL_DIR="${HOME}/.${APP_NAME}-cli"
EXEC="$INSTALL_DIR/$APP_NAME"
CURRENT_PATH="$INSTALL_DIR/current"
BUILD_DIST_DIR="$REPO_ROOT/$BUILD_ROOT_REL/dist"

if [[ ! -f "$ENTRY_PATH" && -z "$WANT_VERSION" ]]; then
  echo "错误: 源码入口不存在：$ENTRY_REL" >&2
  exit 1
fi

# 解析安装来源：默认源码入口；指定版本时识别 onedir / onefile 产物。
pick_source() {
  python3 - "$BUILD_DIST_DIR" "$WANT_VERSION" "$APP_NAME" <<'PY'
import sys
from pathlib import Path
dist = Path(sys.argv[1])
want = sys.argv[2]
app_name = sys.argv[3]

if not want:
    print("source\t\t")
    raise SystemExit(0)

product = dist / want / app_name
if product.is_dir() and (product / app_name).is_file():
    print(f"onedir\t{product}\t{want}")
    raise SystemExit(0)
if product.is_file():
    print(f"onefile\t{product}\t{want}")
    raise SystemExit(0)

print(f"错误: 指定版本产物不存在：{dist}/{want}/{app_name}", file=sys.stderr)
print("可用版本：", file=sys.stderr)
if dist.is_dir():
    for sub in sorted(p for p in dist.iterdir() if p.is_dir()):
        container = sub / app_name
        if container.is_file() or (container.is_dir() and (container / app_name).is_file()):
            print(f"  {sub.name}", file=sys.stderr)
raise SystemExit(1)
PY
}

# write_exec_wrapper: 写稳定包装脚本，转发到已安装的真实执行文件。
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

# write_source_wrapper: 按 entry 生成源码态包装脚本，兼容 package/__main__.py 与普通脚本入口。
write_source_wrapper() {
  local tmp_exec="$EXEC.tmp"
  local module_name=""
  if [[ "$ENTRY_REL" == */__main__.py ]]; then
    module_name="${ENTRY_REL%/__main__.py}"
    module_name="${module_name//\//.}"
  fi

  if [[ -n "$module_name" ]]; then
    cat > "$tmp_exec" <<EOF
#!/usr/bin/env bash
cd "$REPO_ROOT"
exec python3 -m $module_name "\$@"
EOF
  else
    cat > "$tmp_exec" <<EOF
#!/usr/bin/env bash
cd "$REPO_ROOT"
exec python3 "$ENTRY_PATH" "\$@"
EOF
  fi
  chmod +x "$tmp_exec"
  mv "$tmp_exec" "$EXEC"
}

# stage_product: 按产物类型复制到 current 临时目录。
stage_product() {
  local source_kind="$1"
  local source_path="$2"
  local stage_dir="$3"

  rm -rf "$stage_dir"
  mkdir -p "$stage_dir"
  case "$source_kind" in
    onefile)
      cp "$source_path" "$stage_dir/$APP_NAME"
      chmod +x "$stage_dir/$APP_NAME"
      ;;
    onedir)
      cp -R "$source_path" "$stage_dir/$APP_NAME"
      chmod +x "$stage_dir/$APP_NAME/$APP_NAME"
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
    write_exec_wrapper "$CURRENT_PATH/$APP_NAME/$APP_NAME"
  else
    write_exec_wrapper "$CURRENT_PATH/$APP_NAME"
  fi
  INSTALL_MODE="$SOURCE_KIND"
fi

python3 - "$INSTALL_DIR/VERSION.installed" "$INSTALLED_FROM" "$REPO_ROOT" "$BUILD_DIST_DIR" "$INSTALL_MODE" "$APP_NAME" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = {
    "installed_from": sys.argv[2],
    "repo_root": sys.argv[3],
    "build_dist_dir": sys.argv[4],
    "install_mode": sys.argv[5],
    "app_name": sys.argv[6],
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
ln -sf "$EXEC" "$LINK_DIR/$APP_NAME"

echo "已安装：$EXEC"
echo "安装模式：$INSTALL_MODE"
echo "符号链接：$LINK_DIR/$APP_NAME"
if [[ "$LINK_DIR" == "${HOME}/.local/bin" ]]; then
  case ":${PATH}:" in
    *":${HOME}/.local/bin:"*) ;;
    *) echo "提示：${HOME}/.local/bin 不在 PATH，请将其加入 shell 配置" ;;
  esac
fi
echo "请确认 PATH 包含 $LINK_DIR"
