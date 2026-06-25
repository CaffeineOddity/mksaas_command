#!/usr/bin/env bash
# build.sh — 用 PyInstaller 构建 mksaas 发布产物。
# 真相来源：docs/build_install_upgrade_uninstall.md §3/§4
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$REPO_ROOT/build.config.json"

RELEASE=0
BUMP=0
BUMP_LEVEL=""
ONEFILE=0
NEW_CONFIG=0

usage() {
  local default_mode="onedir"
  if [[ -f "$CONFIG_FILE" ]]; then
    default_mode="$(python3 - "$CONFIG_FILE" <<'PY'
import json, sys
try:
    data = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    print("onedir")
else:
    print(data.get("default_bundle_mode", "onedir"))
PY
)"
  fi

  cat <<EOF >&2
用法:
  build.sh [选项]
  build.sh new

开发态继续源码运行；build.sh 主要用于生成发布产物。
默认打包模式由 build.config.json 的 default_bundle_mode 控制（当前: ${default_mode}）；传 --onefile 可强制单文件产物。
构建配置与版本状态统一由仓库根 build.config.json 驱动。

选项:
  new             创建新的 build.config.json 模板
  (无参数)        debug 构建：默认产出 build.config.json 指定模式
                  .build/dist/<version>-dev<next-build>/mksaas/
                  成功后将 next-build 回写到 build.config.json
  --release       release 构建：默认产出 build.config.json 指定模式
                  .build/dist/<version>/mksaas/
                  不递增 build
  --onefile       改为单文件产物：.build/dist/<version>/mksaas
  --bump          提升版本号并重置 build=0 后结束（默认 PATCH+1，不产二进制）
                  可与 --release 组合：先 bump 再产 release 产物
  --minor         与 --bump 组合：提升 MINOR 位并清零 PATCH（0.1.5 → 0.2.0）
  --major         与 --bump 组合：提升 MAJOR 位并清零 MINOR/PATCH（1.2.3 → 2.0.0）
  -h, --help      显示本帮助

示例:
  build.sh new              # 创建新的 build.config.json 模板
  build.sh                  # debug 默认模式构建，产出下一个 dev 号
  build.sh --release        # release 默认模式构建，build 不变
  build.sh --release --onefile
                            # release 单文件构建
  build.sh --bump           # PATCH+1、build=0，不产二进制
  build.sh --bump --minor   # MINOR+1、build=0，不产二进制
  build.sh --bump --release # bump 后产 release 产物

注: --minor / --major 仅在与 --bump 组合时生效，单独使用会报错。
    开发态建议直接运行源码。
    完整规则见 docs/build_install_upgrade_uninstall.md §3/§4
EOF
}

# create_new_config: 在仓库根生成一份新的 build.config.json 模板。
create_new_config() {
  if [[ -e "$CONFIG_FILE" ]]; then
    echo "错误: build.config.json 已存在：$CONFIG_FILE" >&2
    exit 1
  fi

  local default_app_name
  default_app_name="$(basename "$REPO_ROOT")"
  python3 - "$CONFIG_FILE" "$default_app_name" <<'PY'
import json, sys
from pathlib import Path

path = Path(sys.argv[1])
app_name = sys.argv[2]
payload = {
    "app_name": app_name,
    "entry": "main.py",
    "build_root": ".build",
    "default_bundle_mode": "onedir",
    "version": "0.1.0",
    "build": 0,
}
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY
  echo "已创建：$CONFIG_FILE"
  echo "请按需修改 app_name、entry、default_bundle_mode。"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    new) NEW_CONFIG=1; shift ;;
    --release) RELEASE=1; shift ;;
    --onefile) ONEFILE=1; shift ;;
    --bump) BUMP=1; shift ;;
    --minor) BUMP_LEVEL="minor"; shift ;;
    --major) BUMP_LEVEL="major"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ "$NEW_CONFIG" -eq 1 ]]; then
  if [[ "$RELEASE" -eq 1 || "$ONEFILE" -eq 1 || "$BUMP" -eq 1 || -n "$BUMP_LEVEL" ]]; then
    echo "错误: new 不能与其他构建参数组合使用" >&2
    exit 1
  fi
  create_new_config
  exit 0
fi

# --minor / --major 仅在与 --bump 组合时生效
if [[ -n "$BUMP_LEVEL" && "$BUMP" -ne 1 ]]; then
  echo "错误: --minor / --major 必须与 --bump 组合使用" >&2
  exit 1
fi

read_build_config() {
  python3 - "$CONFIG_FILE" <<'PY'
import json, sys
path = sys.argv[1]
d = json.load(open(path, encoding="utf-8"))
print("\t".join([
    d["app_name"],
    d["entry"],
    d.get("build_root", ".build"),
    d.get("default_bundle_mode", "onedir"),
    d["version"],
    str(int(d["build"])),
]))
PY
}

bump_version() {
  local level="${1:-patch}"
  python3 - "$CONFIG_FILE" "$level" <<'PY'
import json, re, sys
path, level = sys.argv[1], sys.argv[2]
d = json.load(open(path, encoding="utf-8"))
m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", d["version"])
major, minor, patch = map(int, m.groups())
if level == "patch":
    patch += 1
elif level == "minor":
    minor += 1; patch = 0
elif level == "major":
    major += 1; minor = 0; patch = 0
d["version"] = f"{major}.{minor}.{patch}"
d["build"] = 0
json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
}

# --bump：提升版本并重置 build=0，回写后即结束（不产二进制，除非同时 --release）
if [[ "$BUMP" -eq 1 ]]; then
  bump_version "$BUMP_LEVEL"
  echo "版本已提升：$(python3 - "$CONFIG_FILE" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print(d["version"], d["build"])
PY
)"
  if [[ "$RELEASE" -ne 1 ]]; then
    exit 0
  fi
fi

IFS=$'\t' read -r APP_NAME ENTRY_REL BUILD_ROOT_REL DEFAULT_BUNDLE_MODE VERSION_STR BUILD_NUM <<<"$(read_build_config)"
ENTRY="$REPO_ROOT/$ENTRY_REL"
BUILD_ROOT="$REPO_ROOT/$BUILD_ROOT_REL"
DIST_ROOT="$BUILD_ROOT/dist"

if [[ ! -f "$ENTRY" ]]; then
  echo "错误: 构建入口不存在：$ENTRY_REL" >&2
  exit 1
fi

if [[ "$DEFAULT_BUNDLE_MODE" != "onedir" && "$DEFAULT_BUNDLE_MODE" != "onefile" ]]; then
  echo "错误: build.config.json 中 default_bundle_mode 仅支持 onedir / onefile" >&2
  exit 1
fi

if [[ "$RELEASE" -eq 1 ]]; then
  PRODUCT_VERSION="$VERSION_STR"
  EFFECTIVE_BUILD="$BUILD_NUM"
else
  EFFECTIVE_BUILD=$((BUILD_NUM + 1))
  PRODUCT_VERSION="${VERSION_STR}-dev${EFFECTIVE_BUILD}"
fi

PRODUCT_DIR="$DIST_ROOT/$PRODUCT_VERSION"
PRODUCT="$PRODUCT_DIR/$APP_NAME"

if [[ "$ONEFILE" -eq 1 ]]; then
  PYI_MODE="--onefile"
  PRODUCT_EXEC="$PRODUCT"
  PRODUCT_KIND="单文件"
else
  PYI_MODE="--$DEFAULT_BUNDLE_MODE"
  if [[ "$DEFAULT_BUNDLE_MODE" == "onefile" ]]; then
    PRODUCT_EXEC="$PRODUCT"
    PRODUCT_KIND="单文件"
  else
    PRODUCT_EXEC="$PRODUCT/$APP_NAME"
    PRODUCT_KIND="目录型"
  fi
fi

# 构建时把真实版本字符串注入 mksaas/_version.py，PyInstaller 会打进二进制
# 这样打包后的 mksaas --version 能读到真实版本，不依赖运行环境的 VERSION 文件
cat > "$REPO_ROOT/mksaas/_version.py" <<EOF
"""mksaas._version — 构建时注入的版本字符串（由 build.sh 生成）。"""

__version__ = "$PRODUCT_VERSION"
EOF

# 校验 PyInstaller
if ! python3 -c "import PyInstaller" 2>/dev/null; then
  echo "PyInstaller 不可用，请先安装：pip install pyinstaller" >&2
  exit 1
fi

rm -rf "$PRODUCT_DIR"
mkdir -p "$PRODUCT_DIR"
mkdir -p "$BUILD_ROOT"
python3 -m PyInstaller \
  "$PYI_MODE" \
  --name "$APP_NAME" \
  --distpath "$PRODUCT_DIR" \
  --workpath "$BUILD_ROOT/work" \
  --specpath "$BUILD_ROOT/spec" \
  "$ENTRY"

if [[ ! -e "$PRODUCT_EXEC" ]]; then
  echo "构建失败：未找到产物 $PRODUCT_EXEC" >&2
  exit 1
fi

# debug 构建成功后回写本次产物号；release 不递增 build
if [[ "$RELEASE" -ne 1 ]]; then
  python3 - "$CONFIG_FILE" "$EFFECTIVE_BUILD" <<'PY'
import json, sys
path = sys.argv[1]
new_build = int(sys.argv[2])
d = json.load(open(path, encoding="utf-8"))
d["build"] = new_build
json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
fi

SIZE=$(du -sh "$PRODUCT" | cut -f1)
echo "构建完成：$PRODUCT ($SIZE)"
echo "产物类型：$PRODUCT_KIND"
echo "可执行文件：$PRODUCT_EXEC"
if [[ "$RELEASE" -ne 1 ]]; then
  echo "提示：开发态推荐直接通过源码运行，无需依赖 build 产物。"
fi
