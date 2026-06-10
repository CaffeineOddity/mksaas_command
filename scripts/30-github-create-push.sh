#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：绑定 GitHub 私有仓库远程并 push 当前项目代码（仓库需提前创建）
# 参数：
#   $1 project_dir
#   $2 repo_url（可选，不传则读取 project.yaml 或交互输入）
# 返回：无
##
set_remote_and_push() {
  local project_dir="$1"
  local repo_url="${2:-}"

  if [[ -z "$repo_url" ]]; then
    repo_url="$(read_project_meta_kv "$project_dir" "REPO_URL")"
  fi

  if [[ -z "$repo_url" ]]; then
    printf "\nGitHub 私有仓库绑定与推送\n" >&2
    open_url "GitHub 新建仓库" "https://github.com/new" >&2
    cat >&2 <<'EOF'
准备步骤（请先在 GitHub 网页完成）：
1. 创建一个新的 Private 空仓库（不要初始化 README / .gitignore / License）。
2. 复制仓库地址（HTTPS 或 SSH 均可），例如：
   - https://github.com/<owner>/<repo>.git
   - git@github.com:<owner>/<repo>.git
EOF
    prompt_input "请输入你的 GitHub 私有仓库地址（repo_url）" repo_url ""
  fi

  if [[ -z "$repo_url" ]]; then
    err "repo_url 不能为空"
    exit 1
  fi

  (
    cd "$project_dir"
    if git remote get-url origin >/dev/null 2>&1; then
      git remote set-url origin "$repo_url"
    else
      git remote add origin "$repo_url"
    fi

    local current_branch
    current_branch="$(git rev-parse --abbrev-ref HEAD)"
    if [[ "$current_branch" == "HEAD" || -z "$current_branch" ]]; then
      current_branch="$(read_project_meta_kv "$project_dir" "TEMPLATE_BRANCH")"
      [[ -z "$current_branch" ]] && current_branch="main"
      git checkout -B "$current_branch" >/dev/null 2>&1 || true
    fi

    git push -u origin "$current_branch" >/dev/null
  )

  upsert_project_meta_kv "$project_dir" "REPO_URL" "$repo_url"

  local repo_page="$repo_url"
  repo_page="${repo_page%.git}"
  if [[ "$repo_page" == git@github.com:* ]]; then
    repo_page="${repo_page#git@github.com:}"
    repo_page="https://github.com/${repo_page}"
  fi
  open_url "仓库页面" "$repo_page" >&2
  printf "%s\n" "$repo_url"
}

main() {
  local project_dir=""
  local repo_url=""

  case "$#" in
    0|1)
      project_dir="$(resolve_existing_project_dir "${1:-}")"
      require_project_meta "$project_dir"
      ;;
    2)
      project_dir="$(resolve_existing_project_dir "$1")"
      repo_url="$2"
      ;;
    *)
      err "用法: $0 [project_dir] | $0 <project_dir> <repo_url>"
      exit 1
      ;;
  esac

  repo_url="$(set_remote_and_push "$project_dir" "$repo_url")"
  printf "%s\n" "$repo_url"
}

main "$@"
