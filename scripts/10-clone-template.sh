#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

TEMPLATE_REPO_DEFAULT="https://github.com/MkSaaSHQ/mksaas-template.git"
TEMPLATE_BRANCH_DEFAULT="main"

##
# 功能：克隆模板仓库，并将模板远程保留为 template（用于后续同步模板变更）
# 参数：
#   $1 template_repo
#   $2 template_branch
#   $3 project_dir
# 返回：无
##
clone_template() {
  local template_repo="$1"
  local template_branch="$2"
  local project_dir="$3"

  if [[ -e "$project_dir" ]]; then
    err "目标目录已存在：$project_dir"
    exit 1
  fi

  printf "\n项目克隆步骤\n"
  open_url "模板仓库" "$template_repo"
  cat <<EOF
执行说明：
1. 即将从模板仓库克隆代码。
2. 分支：${template_branch}
3. 克隆完成后会将 origin 重命名为 template，方便后续从模板拉取更新。
EOF
  git clone --branch "$template_branch" --depth 1 "$template_repo" "$project_dir"
  (
    cd "$project_dir"
    if git remote get-url origin >/dev/null 2>&1; then
      if git remote get-url template >/dev/null 2>&1; then
        git remote remove origin >/dev/null 2>&1 || true
      else
        git remote rename origin template >/dev/null 2>&1 || true
      fi
    fi
  )

  local project_name
  project_name="$(basename "$project_dir")"
  save_project_meta "$project_dir" "$project_name" "$project_name" "" "$template_repo" "$template_branch" "" "" "" ""
}

##
# 功能：解析 project clone 的参数，支持默认模板仓库
# 参数：
#   1 个参数：<project_dir>
#   2 个参数：<template_branch> <project_dir>
#   3 个参数：<template_repo> <template_branch> <project_dir>
# 返回：输出三行，依次为 template_repo/template_branch/project_dir
##
parse_clone_args() {
  local template_repo="$TEMPLATE_REPO_DEFAULT"
  local template_branch="$TEMPLATE_BRANCH_DEFAULT"
  local project_dir=""

  case "$#" in
    1)
      project_dir="$1"
      ;;
    2)
      template_branch="$1"
      project_dir="$2"
      ;;
    3)
      template_repo="$1"
      template_branch="$2"
      project_dir="$3"
      ;;
    *)
      err "用法: $0 <project_dir> | $0 <template_branch> <project_dir> | $0 <template_repo> <template_branch> <project_dir>"
      exit 1
      ;;
  esac

  printf "%s\n%s\n%s\n" "$template_repo" "$template_branch" "$project_dir"
}

main() {
  local parsed=""
  parsed="$(parse_clone_args "$@")"

  local template_repo=""
  local template_branch=""
  local project_dir=""
  IFS=$'\n' read -r template_repo template_branch project_dir <<< "$parsed"

  clone_template "$template_repo" "$template_branch" "$project_dir"
}

main "$@"
