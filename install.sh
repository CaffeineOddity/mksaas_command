#!/usr/bin/env bash
# install.sh — 本地目录 + 符号链接安装 mksaas。
# 真相来源：docs/build_install_upgrade_uninstall.md §5/§6
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.mksaas-cli"
EXEC="$INSTALL_DIR/mksaas"

# 来源判定：dist 下最新版本产物优先；否则安装源码入口（开发态）
pick_source() {
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
