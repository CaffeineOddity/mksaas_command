#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：交互式写入 Vercel 部署所需的基础 URL
# 参数：$1 project_dir
# 返回：无
##
configure_vercel_deploy() {
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
    current_prod_base_url="https://YOUR-PROJECT.vercel.app"
  fi

  printf "\n配置 Vercel 部署\n"
  open_url "Vercel Dashboard" "https://vercel.com/dashboard"
  open_url "MkSaaS Vercel 部署文档" "https://mksaas.com/zh/docs/deployment/vercel"
  cat <<'EOF'
申请步骤：
1. 在 Vercel Dashboard 点击 Add New Project。
2. 导入你的 GitHub 仓库。
3. Framework 选择 Next.js，安装命令用 pnpm install，构建命令用 pnpm build。
4. 在 Environment Variables 中填入 .env 里的生产变量。
5. 首次部署完成后，确认线上域名，再回填 NEXT_PUBLIC_BASE_URL。
EOF
  prompt_input "生产环境 Base URL（用于部署平台 NEXT_PUBLIC_BASE_URL）" prod_base_url "$current_prod_base_url"
  upsert_project_meta_kv "$project_dir" "PROD_BASE_URL" "$prod_base_url"
  upsert_profile_env_kv "$project_dir" "prod" "NEXT_PUBLIC_BASE_URL" "$prod_base_url"
  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  printf "生产环境 Base URL：%s\n" "$prod_base_url"
  printf "文档：https://mksaas.com/zh/docs/deployment/vercel\n"
  printf "建议在 Vercel Project Settings -> Environment Variables 设置：NEXT_PUBLIC_BASE_URL=%s\n" "$prod_base_url"
}

main() {
  local project_dir=""

  if [[ $# -gt 1 ]]; then
    err "用法: $0 [project_dir]"
    exit 1
  fi

  project_dir="$(resolve_existing_project_dir "${1:-}")"
  configure_vercel_deploy "$project_dir"
}

main "$@"
