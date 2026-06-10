#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：交互式写入 Google OAuth 环境变量并输出回调地址
# 参数：$1 [profile], $2 [project_dir]
# 返回：无
##
configure_google_oauth() {
  local profile="$1"
  local project_dir="$2"
  local env_file
  env_file="$(get_profile_env_file "$project_dir" "$profile")"

  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  local current_client_id
  local current_client_secret
  local base_url
  current_client_id="$(read_profile_env_kv "$project_dir" "$profile" "GOOGLE_CLIENT_ID")"
  current_client_secret="$(read_profile_env_kv "$project_dir" "$profile" "GOOGLE_CLIENT_SECRET")"
  if [[ -z "$current_client_id" && -f "$env_file" ]]; then
    current_client_id="$(read_env_kv "$env_file" "GOOGLE_CLIENT_ID")"
  fi
  if [[ -z "$current_client_secret" && -f "$env_file" ]]; then
    current_client_secret="$(read_env_kv "$env_file" "GOOGLE_CLIENT_SECRET")"
  fi

  base_url="$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_BASE_URL")"
  if [[ -z "$base_url" ]]; then
    if [[ "$profile" == "prod" ]]; then
      base_url="$(read_project_meta_kv "$project_dir" "PROD_BASE_URL")"
    else
      base_url="$(read_project_meta_kv "$project_dir" "DEV_BASE_URL")"
    fi
  fi

  local client_id=""
  local client_secret=""
  printf "\n配置 Google OAuth\n"
  open_url "Google Cloud Credentials" "https://console.cloud.google.com/apis/credentials"
  open_url "MkSaaS Auth 文档" "https://mksaas.com/zh/docs/auth"
  cat <<EOF
申请步骤：
1. 在 Google Cloud 中创建或选择一个项目。
2. 先配置 OAuth consent screen，用户类型通常选 External。
3. 再创建 OAuth Client ID，应用类型选 Web application。
4. Authorized JavaScript origins 填：${base_url}
5. Authorized redirect URI 填：${base_url}/api/auth/callback/google
6. 创建后复制 Client ID 和 Client Secret。
EOF
  prompt_input "Google Client ID" client_id "$current_client_id"
  prompt_input "Google Client Secret" client_secret "$current_client_secret" "true"

  upsert_profile_env_kv "$project_dir" "$profile" "GOOGLE_CLIENT_ID" "$client_id"
  upsert_profile_env_kv "$project_dir" "$profile" "GOOGLE_CLIENT_SECRET" "$client_secret"
  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  printf "已保存敏感配置到：%s\n" "$(get_profile_secrets_env_file "$project_dir" "$profile")"
  printf "已生成环境文件：%s\n" "$(get_profile_env_file "$project_dir" "$profile")"
  printf "回调 URL：%s/api/auth/callback/google\n" "$base_url"
  printf "文档：https://mksaas.com/zh/docs/auth\n"
}

main() {
  local project_dir=""
  local profile="test"

  if [[ $# -gt 2 ]]; then
    err "用法: $0 [profile] [project_dir]"
    exit 1
  fi

  IFS=$'\n' read -r profile project_dir < <(parse_profile_and_project_dir "${1:-}" "${2:-}")
  configure_google_oauth "$profile" "$project_dir"
}

main "$@"
