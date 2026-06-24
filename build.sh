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
  echo "用法: build.sh [--release] [--bump [--minor|--major]]" >&2
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
