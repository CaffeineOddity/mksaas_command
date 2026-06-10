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
# 功能：配置 Stripe 支付（写入 Stripe key、Webhook secret、价格 ID）
# 参数：$1 [profile], $2 [project_dir]
# 返回：无
##
configure_stripe_payment() {
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

  printf "\n配置支付：Stripe\n"
  open_url "Stripe Dashboard" "https://dashboard.stripe.com/"
  open_url "Stripe API Keys" "https://dashboard.stripe.com/apikeys"
  open_url "Stripe Webhooks" "https://dashboard.stripe.com/webhooks"
  open_url "Stripe 产品（Product Catalog）" "https://dashboard.stripe.com/products"
  open_url "MkSaaS Stripe 文档" "https://mksaas.com/docs/payment/stripe"
  open_url "MkSaaS 环境变量（支付）" "https://mksaas.com/zh/docs/env#%E6%94%AF%E4%BB%98"
  cat <<EOF
申请步骤：
1. 在 Stripe Dashboard -> Developers -> API keys 复制 Secret key，填入 STRIPE_SECRET_KEY。
2. 在 Stripe Dashboard -> Developers -> Webhooks 创建 endpoint：
   - Webhook URL: ${base_url}/api/webhooks/stripe
   - 事件：invoice.paid、checkout.session.completed、customer.subscription.created/updated/deleted
   - Reveal Signing Secret，填入 STRIPE_WEBHOOK_SECRET
3. 在 Product Catalog 创建产品与价格，并把 price_... 填入价格变量：
   - NEXT_PUBLIC_STRIPE_PRICE_PRO_MONTHLY
   - NEXT_PUBLIC_STRIPE_PRICE_PRO_YEARLY
   - NEXT_PUBLIC_STRIPE_PRICE_LIFETIME
EOF

  local stripe_secret_key
  local stripe_webhook_secret
  local pro_monthly
  local pro_yearly
  local lifetime

  stripe_secret_key="$(read_profile_env_kv "$project_dir" "$profile" "STRIPE_SECRET_KEY")"
  stripe_webhook_secret="$(read_profile_env_kv "$project_dir" "$profile" "STRIPE_WEBHOOK_SECRET")"
  pro_monthly="$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_STRIPE_PRICE_PRO_MONTHLY")"
  pro_yearly="$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_STRIPE_PRICE_PRO_YEARLY")"
  lifetime="$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_STRIPE_PRICE_LIFETIME")"

  local input=""
  prompt_input "STRIPE_SECRET_KEY" input "$stripe_secret_key" "true"
  upsert_profile_env_kv "$project_dir" "$profile" "STRIPE_SECRET_KEY" "$input"

  prompt_input "STRIPE_WEBHOOK_SECRET（whsec_...）" input "$stripe_webhook_secret" "true"
  upsert_profile_env_kv "$project_dir" "$profile" "STRIPE_WEBHOOK_SECRET" "$input"

  prompt_input "NEXT_PUBLIC_STRIPE_PRICE_PRO_MONTHLY（price_...）" input "$pro_monthly"
  upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_STRIPE_PRICE_PRO_MONTHLY" "$input"

  prompt_input "NEXT_PUBLIC_STRIPE_PRICE_PRO_YEARLY（price_...）" input "$pro_yearly"
  upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_STRIPE_PRICE_PRO_YEARLY" "$input"

  prompt_input "NEXT_PUBLIC_STRIPE_PRICE_LIFETIME（price_...）" input "$lifetime"
  upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_STRIPE_PRICE_LIFETIME" "$input"

  upsert_project_meta_kv "$project_dir" "PAYMENT_PROVIDER" "stripe"
  upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_PAYMENT_PROVIDER" "stripe"
  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  printf "已保存配置到：%s（敏感值会写入 secrets.*.env）\n" "${project_dir}/.mksaas"
  printf "已生成环境文件：%s\n" "$(get_profile_env_file "$project_dir" "$profile")"
  if [[ "$profile" == "test" && "$base_url" == http://localhost:* ]]; then
    printf "提示：Stripe Webhook 不能直接回调 localhost，通常需要用 Stripe CLI（stripe listen）或公网域名。\n"
  fi
  printf "Webhook URL：%s/api/webhooks/stripe\n" "$base_url"
}

main() {
  local project_dir=""
  local profile="test"

  if [[ $# -gt 2 ]]; then
    err "用法: $0 [profile] [project_dir]"
    exit 1
  fi

  IFS=$'\n' read -r profile project_dir < <(parse_profile_and_project_dir "${1:-}" "${2:-}")
  configure_stripe_payment "$profile" "$project_dir"
}

main "$@"
