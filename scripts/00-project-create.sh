#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

TEMPLATE_REPO_DEFAULT="https://github.com/MkSaaSHQ/mksaas-template.git"
TEMPLATE_BRANCH_DEFAULT="main"

##
# 功能：仅创建项目骨架目录与项目配置文件
# 参数：$1 project_name
# 返回：无
##
create_project_skeleton() {
  local project_name="$1"
  local project_dir="$(pwd)/${project_name}"

  if [[ -z "$project_name" ]]; then
    err "项目名不能为空"
    exit 1
  fi

  if [[ -e "$project_dir" ]]; then
    err "目标目录已存在：$project_dir"
    exit 1
  fi

  mkdir -p "$project_dir"
  save_project_meta "$project_dir" "$project_name" "$project_name" "" "$TEMPLATE_REPO_DEFAULT" "$TEMPLATE_BRANCH_DEFAULT" "" "" "" ""

  printf "已创建项目骨架：%s\n" "$project_dir"
  printf "项目配置文件：%s\n" "$(get_project_meta_file "$project_dir")"
}

main() {
  local project_name="${1:-}"

  if [[ $# -gt 1 ]]; then
    err "用法: $0 [project_name]"
    exit 1
  fi

  if [[ -z "$project_name" ]]; then
    prompt_input "项目目录名（本地文件夹名）" project_name ""
  fi

  create_project_skeleton "$project_name"
}

main "$@"

