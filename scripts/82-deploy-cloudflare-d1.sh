#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：输出 Cloudflare Workers（D1）部署提示并更新生产域名
# 参数：$1 project_dir
# 返回：无
##
configure_cloudflare_d1_deploy() {
  local project_dir="$1"
  local env_file="${project_dir}/.env"

  if [[ ! -f "$env_file" ]]; then
    err "未找到环境文件：$env_file"
    exit 1
  fi

  local prod_base_url=""
  local current_prod_base_url
  current_prod_base_url="$(read_project_meta_kv "$project_dir" "PROD_BASE_URL")"
  if [[ -z "$current_prod_base_url" ]]; then
    current_prod_base_url="https://YOUR-DOMAIN.com"
  fi

  printf "\n配置 Cloudflare Workers（D1）部署\n"
  open_url "Cloudflare Dashboard" "https://dash.cloudflare.com/"
  open_url "MkSaaS Cloudflare D1 部署文档" "https://mksaas.com/zh/docs/deployment/cloudflare-d1"
  cat <<'EOF'
申请步骤：
1. 确认你使用的是模板的 cloudflare-d1 分支。
2. 在 Cloudflare 中创建 Worker。
3. 创建 D1 数据库，并按文档把 D1 绑定到 Worker。
4. 配置项目所需的环境变量和域名。
5. 部署完成后确认 NEXT_PUBLIC_BASE_URL 为线上域名。
EOF
  prompt_input "生产环境 Base URL（用于部署平台 NEXT_PUBLIC_BASE_URL）" prod_base_url "$current_prod_base_url"
  upsert_project_meta_kv "$project_dir" "PROD_BASE_URL" "$prod_base_url"
  upsert_profile_env_kv "$project_dir" "prod" "NEXT_PUBLIC_BASE_URL" "$prod_base_url"
  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  printf "生产环境 Base URL：%s\n" "$prod_base_url"
  printf "文档：https://mksaas.com/zh/docs/deployment/cloudflare-d1\n"
  printf "重要：该部署模式必须使用模板的 cloudflare-d1 分支，并手动绑定 D1 数据库。\n"
}

main() {
  local project_dir=""

  if [[ $# -gt 1 ]]; then
    err "用法: $0 [project_dir]"
    exit 1
  fi

  project_dir="$(resolve_existing_project_dir "${1:-}")"
  configure_cloudflare_d1_deploy "$project_dir"
}

main "$@"
