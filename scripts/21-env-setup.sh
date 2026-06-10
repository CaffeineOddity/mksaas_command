#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：交互式配置某个环境 Profile（test/prod），并将结果写入 project.yaml，最后重新生成 .env.test/.env.prod
# 参数：$1 [profile], $2 [project_dir]
# 返回：无
##
configure_env_profile() {
  local profile="$1"
  local project_dir="$2"

  require_project_meta "$project_dir"

  if ! is_valid_profile "$profile"; then
    local which
    which="$(choose_option "你要配置哪个环境？" "1" "测试/开发（test）" "正式/生产（prod）")"
    if [[ "$which" == "正式/生产（prod）" ]]; then
      profile="prod"
    else
      profile="test"
    fi
  fi

  local current_base_url
  current_base_url="$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_BASE_URL")"
  if [[ -z "$current_base_url" ]]; then
    if [[ "$profile" == "prod" ]]; then
      current_base_url="$(read_project_meta_kv "$project_dir" "PROD_BASE_URL")"
    else
      current_base_url="$(read_project_meta_kv "$project_dir" "DEV_BASE_URL")"
    fi
  fi

  local base_url_default="$current_base_url"
  if [[ -z "$base_url_default" ]]; then
    if [[ "$profile" == "prod" ]]; then
      base_url_default="https://YOUR-DOMAIN.com"
    else
      base_url_default="http://localhost:3000"
    fi
  fi

  local base_url=""
  if [[ "$profile" == "prod" ]]; then
    prompt_input "正式/生产 Base URL（用于 .env.prod 的 NEXT_PUBLIC_BASE_URL）" base_url "$base_url_default"
  else
    prompt_input "测试/开发 Base URL（用于 .env.test 的 NEXT_PUBLIC_BASE_URL）" base_url "$base_url_default"
  fi

  upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_BASE_URL" "$base_url"

  local run_more
  run_more="$(choose_option "是否继续配置该环境的其他模块（数据库/OAuth/邮件/支付等）？" "2" "是" "否")"
  if [[ "$run_more" == "否" ]]; then
    "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true
    printf "已生成环境文件：%s、%s，并同步 .env 为 .env.test\n" "${project_dir}/.env.test" "${project_dir}/.env.prod"
    return 0
  fi

  local db_choice=""
  db_choice="$(choose_option "是否配置数据库（DATABASE_URL）？" "2" "Neon" "Supabase" "本地 Docker Postgres" "跳过")"
  case "$db_choice" in
    Neon)
      "${SCRIPT_DIR}/70-database-neon.sh" "$profile" "$project_dir"
      ;;
    Supabase)
      "${SCRIPT_DIR}/71-database-supabase.sh" "$profile" "$project_dir"
      ;;
    "本地 Docker Postgres")
      "${SCRIPT_DIR}/72-database-local-postgres.sh" "$profile" "$project_dir"
      ;;
    跳过)
      ;;
  esac

  local r2_choice turnstile_choice
  r2_choice="$(choose_option "是否配置 Cloudflare R2 存储？" "2" "是" "否")"
  [[ "$r2_choice" == "是" ]] && "${SCRIPT_DIR}/50-cloudflare-r2.sh" "$profile" "$project_dir"

  turnstile_choice="$(choose_option "是否配置 Cloudflare Turnstile 验证码？" "2" "是" "否")"
  [[ "$turnstile_choice" == "是" ]] && "${SCRIPT_DIR}/60-cloudflare-turnstile.sh" "$profile" "$project_dir"

  local oauth_github_choice oauth_google_choice
  oauth_github_choice="$(choose_option "是否配置 GitHub OAuth？" "2" "是" "否")"
  [[ "$oauth_github_choice" == "是" ]] && "${SCRIPT_DIR}/90-auth-github.sh" "$profile" "$project_dir"

  oauth_google_choice="$(choose_option "是否配置 Google OAuth？" "2" "是" "否")"
  [[ "$oauth_google_choice" == "是" ]] && "${SCRIPT_DIR}/91-auth-google.sh" "$profile" "$project_dir"

  local email_choice newsletter_choice
  email_choice="$(choose_option "是否配置邮件服务（Resend）？" "2" "是" "否")"
  [[ "$email_choice" == "是" ]] && "${SCRIPT_DIR}/100-email-resend.sh" "$profile" "$project_dir"

  newsletter_choice="$(choose_option "是否配置 Newsletter（邮件订阅）？" "2" "是" "否")"
  [[ "$newsletter_choice" == "是" ]] && "${SCRIPT_DIR}/101-newsletter-setup.sh" "$profile" "$project_dir"

  local payment_choice
  payment_choice="$(choose_option "是否配置支付/订阅？" "3" "Stripe" "Creem" "跳过")"
  case "$payment_choice" in
    Stripe)
      "${SCRIPT_DIR}/110-payment-stripe.sh" "$profile" "$project_dir"
      ;;
    Creem)
      "${SCRIPT_DIR}/111-payment-creem.sh" "$profile" "$project_dir"
      ;;
    跳过)
      ;;
  esac

  local notification_choice credits_choice analytics_choice affiliates_choice
  notification_choice="$(choose_option "是否配置支付通知（Discord/飞书）？" "2" "是" "否")"
  [[ "$notification_choice" == "是" ]] && "${SCRIPT_DIR}/120-notification-setup.sh" "$profile" "$project_dir"

  credits_choice="$(choose_option "是否配置积分（Credits）？" "2" "是" "否")"
  [[ "$credits_choice" == "是" ]] && "${SCRIPT_DIR}/130-credits-setup.sh" "$profile" "$project_dir"

  analytics_choice="$(choose_option "是否配置统计分析（Analytics）？" "2" "是" "否")"
  [[ "$analytics_choice" == "是" ]] && "${SCRIPT_DIR}/140-analytics-setup.sh" "$profile" "$project_dir"

  affiliates_choice="$(choose_option "是否配置联盟营销（Affiliates）？" "2" "是" "否")"
  [[ "$affiliates_choice" == "是" ]] && "${SCRIPT_DIR}/150-affiliates-setup.sh" "$profile" "$project_dir"

  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true
  printf "已完成 %s 环境配置，并生成：%s\n" "$profile" "$(get_profile_env_file "$project_dir" "$profile")"
}

main() {
  local profile="${1:-}"
  local project_dir=""

  if [[ $# -gt 2 ]]; then
    err "用法: $0 [profile] [project_dir]"
    exit 1
  fi

  if is_valid_profile "$profile"; then
    project_dir="$(resolve_existing_project_dir "${2:-}")"
  else
    project_dir="$(resolve_existing_project_dir "${1:-}")"
    profile=""
  fi

  configure_env_profile "$profile" "$project_dir"
}

main "$@"

