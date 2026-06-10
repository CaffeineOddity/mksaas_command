#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

##
# 功能：兼容入口，转发到 main.sh（交互式流程）
# 参数：$@
# 返回：main.sh 的退出码
##
main() {
  local script_dir
  local source="${BASH_SOURCE[0]}"
  while [[ -h "$source" ]]; do
    local dir
    dir="$(cd -P "$(dirname "$source")" && pwd)"
    source="$(readlink "$source")"
    [[ "$source" != /* ]] && source="${dir}/${source}"
  done
  script_dir="$(cd -P "$(dirname "$source")" && pwd)"
  exec "${script_dir}/main.sh" "$@"
}

main "$@"
