#!/usr/bin/env bash
# build.sh — 用 PyInstaller 构建 mksaas 单文件二进制。
# 真相来源：docs/build_install_upgrade_uninstall.md §3/§4
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION_FILE="$REPO_ROOT/VERSION"
ENTRY="$REPO_ROOT/mksaas/__main__.py"
DIST_ROOT="$REPO_ROOT/dist"

RELEASE=0
BUMP=0
BUMP_LEVEL=""

usage() {
  cat <<'EOF' >&2
用法: build.sh [选项]

用 PyInstaller 把 mksaas 打包为单文件二进制，产物落 dist/<版本>/mksaas。
版本由仓库根 VERSION 文件的 version(MAJOR.MINOR.PATCH) 与 build(整数) 驱动。

选项:
  (无参数)        debug 构建：产物 dist/<version>-dev<build>/mksaas，
                  构建完成后 build 自动 +1 回写 VERSION
  --release       release 构建：产物 dist/<version>/mksaas，不递增 build
  --bump          提升版本号并重置 build=1 后结束（默认 PATCH+1，不产二进制）
                  可与 --release 组合：先 bump 再产 release 产物
  --minor         与 --bump 组合：提升 MINOR 位并清零 PATCH（0.1.5 → 0.2.0）
  --major         与 --bump 组合：提升 MAJOR 位并清零 MINOR/PATCH（1.2.3 → 2.0.0）
  -h, --help      显示本帮助

示例:
  build.sh                  # debug 构建，build+1
  build.sh --release        # release 构建，build 不变
  build.sh --bump           # PATCH+1、build=1，不产二进制
  build.sh --bump --minor   # MINOR+1、build=1，不产二进制
  build.sh --bump --release # bump 后产 release 产物

注: --minor / --major 仅在与 --bump 组合时生效，单独使用会报错。
    完整规则见 docs/build_install_upgrade_uninstall.md §3/§4
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --release) RELEASE=1; shift ;;
    --bump) BUMP=1; shift ;;
    --minor) BUMP_LEVEL="minor"; shift ;;
    --major) BUMP_LEVEL="major"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数: $1" >&2; usage; exit 1 ;;
  esac
done

# --minor / --major 仅在与 --bump 组合时生效
if [[ -n "$BUMP_LEVEL" && "$BUMP" -ne 1 ]]; then
  echo "错误: --minor / --major 必须与 --bump 组合使用" >&2
  exit 1
fi

read_version() {
  python3 - "$VERSION_FILE" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print(d["version"], d["build"])
PY
}

bump_version() {
  local level="${1:-patch}"
  python3 - "$VERSION_FILE" "$level" <<'PY'
import json, re, sys
path, level = sys.argv[1], sys.argv[2]
d = json.load(open(path))
m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", d["version"])
major, minor, patch = map(int, m.groups())
if level == "patch":
    patch += 1
elif level == "minor":
    minor += 1; patch = 0
elif level == "major":
    major += 1; minor = 0; patch = 0
d["version"] = f"{major}.{minor}.{patch}"
d["build"] = 1
json.dump(d, open(path, "w"), ensure_ascii=False, indent=2)
PY
}

# --bump：提升版本并重置 build=1，回写后即结束（不产二进制，除非同时 --release）
if [[ "$BUMP" -eq 1 ]]; then
  bump_version "$BUMP_LEVEL"
  echo "版本已提升：$(read_version)"
  if [[ "$RELEASE" -ne 1 ]]; then
    exit 0
  fi
fi

read VERSION_STR BUILD_NUM <<<"$(read_version)"

if [[ "$RELEASE" -eq 1 ]]; then
  PRODUCT_VERSION="$VERSION_STR"
else
  PRODUCT_VERSION="${VERSION_STR}-dev${BUILD_NUM}"
fi

PRODUCT_DIR="$DIST_ROOT/$PRODUCT_VERSION"
PRODUCT="$PRODUCT_DIR/mksaas"

# 校验 PyInstaller
if ! python3 -c "import PyInstaller" 2>/dev/null; then
  echo "PyInstaller 不可用，请先安装：pip install pyinstaller" >&2
  exit 1
fi

mkdir -p "$PRODUCT_DIR"
python3 -m PyInstaller \
  --onefile \
  --name mksaas \
  --distpath "$PRODUCT_DIR" \
  --workpath "$REPO_ROOT/build" \
  --specpath "$REPO_ROOT/build" \
  "$ENTRY"

# debug 构建完成后 build+1 回写；release 不递增
if [[ "$RELEASE" -ne 1 ]]; then
  python3 - "$VERSION_FILE" <<'PY'
import json, sys
path = sys.argv[1]
d = json.load(open(path))
d["build"] = int(d["build"]) + 1
json.dump(d, open(path, "w"), ensure_ascii=False, indent=2)
PY
fi

SIZE=$(du -h "$PRODUCT" | cut -f1)
echo "构建完成：$PRODUCT ($SIZE)"
