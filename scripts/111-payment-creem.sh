#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：获取指定 Profile Base URL（优先 project.yaml env，其次 DEV_BASE_URL/PROD_BASE_URL）
# 参数：$1 project_dir, $2 profile
# 返回：输出 base_url
##
get_profile_base_url() {
  local project_dir="$1"
  local profile="${2:-prod}"
  local base_url
  base_url="$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_BASE_URL")"
  if [[ -n "$base_url" ]]; then
    printf "%s" "$base_url"
    return 0
  fi

  if [[ "$profile" == "prod" ]]; then
    printf "%s" "$(read_project_meta_kv "$project_dir" "PROD_BASE_URL")"
  else
    printf "%s" "$(read_project_meta_kv "$project_dir" "DEV_BASE_URL")"
  fi
}

##
# 功能：配置 Creem 支付（写入 CREEM_API_KEY、CREEM_WEBHOOK_SECRET、产品 ID）
# 参数：$1 [profile], $2 [project_dir]
# 返回：无
##
configure_creem_payment() {
  local profile="$1"
  local project_dir="$2"
  local env_file
  env_file="$(get_profile_env_file "$project_dir" "$profile")"

  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  local base_url
  base_url="$(get_profile_base_url "$project_dir" "$profile")"
  if [[ -z "$base_url" ]]; then
    if [[ "$profile" == "prod" ]]; then
      prompt_input "正式/生产 Base URL（用于 Webhook URL）" base_url "https://YOUR-DOMAIN.com"
    else
      prompt_input "测试/开发 Base URL（用于 Webhook URL）" base_url "http://localhost:3000"
    fi
    upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_BASE_URL" "$base_url"
  fi

  printf "\n配置支付：Creem\n"
  open_url "Creem" "https://creem.io/"
  open_url "MkSaaS Creem 文档" "https://mksaas.com/docs/payment/creem"
  cat <<EOF
申请步骤：
1. 在 Creem Dashboard -> Developers -> API & Webhooks 创建 API Key，填入 CREEM_API_KEY。
2. 创建 Webhook：
   - Webhook URL: ${base_url}/api/webhooks/creem
   - 复制 Webhook signing secret，填入 CREEM_WEBHOOK_SECRET
3. 创建产品（Products）并复制 Product ID（prod_...）：
   - VITE_CREEM_PRODUCT_PRO_MONTHLY
   - VITE_CREEM_PRODUCT_PRO_YEARLY
   - VITE_CREEM_PRODUCT_LIFETIME
4. 支付 Provider 变量：VITE_PAYMENT_PROVIDER=creem
EOF

  local input=""
  prompt_input "CREEM_API_KEY（creem_test_... 或 creem_live_...）" input "$(read_profile_env_kv "$project_dir" "$profile" "CREEM_API_KEY")" "true"
  upsert_profile_env_kv "$project_dir" "$profile" "CREEM_API_KEY" "$input"

  prompt_input "CREEM_WEBHOOK_SECRET" input "$(read_profile_env_kv "$project_dir" "$profile" "CREEM_WEBHOOK_SECRET")" "true"
  upsert_profile_env_kv "$project_dir" "$profile" "CREEM_WEBHOOK_SECRET" "$input"

  prompt_input "VITE_CREEM_PRODUCT_PRO_MONTHLY（prod_...）" input "$(read_profile_env_kv "$project_dir" "$profile" "VITE_CREEM_PRODUCT_PRO_MONTHLY")"
  upsert_profile_env_kv "$project_dir" "$profile" "VITE_CREEM_PRODUCT_PRO_MONTHLY" "$input"

  prompt_input "VITE_CREEM_PRODUCT_PRO_YEARLY（prod_...）" input "$(read_profile_env_kv "$project_dir" "$profile" "VITE_CREEM_PRODUCT_PRO_YEARLY")"
  upsert_profile_env_kv "$project_dir" "$profile" "VITE_CREEM_PRODUCT_PRO_YEARLY" "$input"

  prompt_input "VITE_CREEM_PRODUCT_LIFETIME（prod_...）" input "$(read_profile_env_kv "$project_dir" "$profile" "VITE_CREEM_PRODUCT_LIFETIME")"
  upsert_profile_env_kv "$project_dir" "$profile" "VITE_CREEM_PRODUCT_LIFETIME" "$input"

  upsert_profile_env_kv "$project_dir" "$profile" "VITE_PAYMENT_PROVIDER" "creem"
  upsert_project_meta_kv "$project_dir" "PAYMENT_PROVIDER" "creem"
  upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_PAYMENT_PROVIDER" "creem"
  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  printf "已保存配置到：%s（敏感值会写入 secrets.*.env）\n" "${project_dir}/.mksaas"
  printf "已生成环境文件：%s\n" "$(get_profile_env_file "$project_dir" "$profile")"
  if [[ "$profile" == "test" && "$base_url" == http://localhost:* ]]; then
    printf "提示：Webhook 不能直接回调 localhost，通常需要公网域名或本地转发工具。\n"
  fi
  printf "Webhook URL：%s/api/webhooks/creem\n" "$base_url"
}

main() {
  local project_dir=""
  local profile="test"

  if [[ $# -gt 2 ]]; then
    err "用法: $0 [profile] [project_dir]"
    exit 1
  fi

  IFS=$'\n' read -r profile project_dir < <(parse_profile_and_project_dir "${1:-}" "${2:-}")
  configure_creem_payment "$profile" "$project_dir"
}

main "$@"
