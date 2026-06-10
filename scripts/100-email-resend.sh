#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：配置 Resend 邮件服务（写入 RESEND_API_KEY）
# 参数：$1 [profile], $2 [project_dir]
# 返回：无
##
configure_resend_email() {
  local profile="$1"
  local project_dir="$2"
  local env_file
  env_file="$(get_profile_env_file "$project_dir" "$profile")"

  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  local current_key
  current_key="$(read_profile_env_kv "$project_dir" "$profile" "RESEND_API_KEY")"
  if [[ -z "$current_key" && -f "$env_file" ]]; then
    current_key="$(read_env_kv "$env_file" "RESEND_API_KEY")"
  fi
  local api_key=""

  printf "\n配置邮件服务：Resend\n"
  open_url "Resend 控制台" "https://resend.com/"
  open_url "Resend API Keys" "https://resend.com/api-keys"
  open_url "MkSaaS Email 文档" "https://mksaas.com/docs/email"
  open_url "MkSaaS 环境变量（邮件）" "https://mksaas.com/zh/docs/env#%E9%82%AE%E4%BB%B6"
  cat <<'EOF'
申请步骤：
1. 登录 Resend 后进入 API Keys，创建一个 API Key（权限可选 Send emails 或 Full access）。
2. 把 API Key 填入 RESEND_API_KEY。
3. 如果你需要发给非自己邮箱，通常还需要在 Resend 里验证发信域名（Domains）。
EOF

  prompt_input "RESEND_API_KEY" api_key "$current_key" "true"
  upsert_profile_env_kv "$project_dir" "$profile" "RESEND_API_KEY" "$api_key"
  upsert_project_meta_kv "$project_dir" "EMAIL_PROVIDER" "resend"
  upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_EMAIL_PROVIDER" "resend"
  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  printf "已保存敏感配置到：%s\n" "$(get_profile_secrets_env_file "$project_dir" "$profile")"
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
  configure_resend_email "$profile" "$project_dir"
}

main "$@"
