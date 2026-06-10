#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：交互式写入 Cloudflare R2 相关环境变量
# 参数：
#   $1 [profile], $2 [project_dir]
# 返回：无
##
configure_cloudflare_r2() {
  local profile="$1"
  local project_dir="$2"

  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  local storage_region=""
  local bucket_name=""
  local access_key_id=""
  local secret_access_key=""
  local endpoint=""
  local public_url=""

  printf "\n配置 Cloudflare R2\n"
  open_url "Cloudflare R2 控制台" "https://dash.cloudflare.com/?to=/:account/r2/overview"
  open_url "MkSaaS 环境变量文档" "https://mksaas.com/zh/docs/env"
  cat <<'EOF'
申请步骤：
1. 在 Cloudflare 控制台进入 R2，先创建一个 Bucket。
2. 在 R2 的 API Tokens / Manage R2 API Tokens 页面创建 Access Key。
3. 记录 Bucket 名称、Access Key ID、Secret Access Key。
4. 复制 S3 Endpoint，格式通常是 https://<accountid>.r2.cloudflarestorage.com
5. 如果你有 CDN 或公开访问域名，再填写 Public URL；没有可以先留空。
EOF
  prompt_input "R2 区域（例如 auto）" storage_region "auto"
  prompt_input "R2 Bucket 名称" bucket_name ""
  prompt_input "R2 Access Key ID" access_key_id "" "true"
  prompt_input "R2 Secret Access Key" secret_access_key "" "true"
  prompt_input "R2 S3 Endpoint（例如 https://<accountid>.r2.cloudflarestorage.com）" endpoint ""
  prompt_input "R2 Public URL（可留空）" public_url ""

  upsert_profile_env_kv "$project_dir" "$profile" "STORAGE_REGION" "$storage_region"
  upsert_profile_env_kv "$project_dir" "$profile" "STORAGE_BUCKET_NAME" "$bucket_name"
  upsert_profile_env_kv "$project_dir" "$profile" "STORAGE_ACCESS_KEY_ID" "$access_key_id"
  upsert_profile_env_kv "$project_dir" "$profile" "STORAGE_SECRET_ACCESS_KEY" "$secret_access_key"
  upsert_profile_env_kv "$project_dir" "$profile" "STORAGE_ENDPOINT" "$endpoint"
  upsert_profile_env_kv "$project_dir" "$profile" "STORAGE_PUBLIC_URL" "$public_url"
  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  printf "已保存配置到：%s（敏感值会写入 secrets.*.env）\n" "${project_dir}/.mksaas"
  printf "已生成环境文件：%s\n" "$(get_profile_env_file "$project_dir" "$profile")"
}

main() {
  local project_dir=""
  local profile="test"

  if [[ $# -gt 2 ]]; then
    err "用法: $0 [profile] [project_dir]"
    exit 1
  fi

  IFS=$'\n' read -r profile project_dir < <(parse_profile_and_project_dir "${1:-}" "${2:-}")
  configure_cloudflare_r2 "$profile" "$project_dir"
}

main "$@"
