#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：配置 Newsletter（Resend/Beehiiv），写入对应环境变量
# 参数：$1 [profile], $2 [project_dir]
# 返回：无
##
configure_newsletter() {
  local profile="$1"
  local project_dir="$2"
  local env_file
  env_file="$(get_profile_env_file "$project_dir" "$profile")"

  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  printf "\n配置邮件订阅（Newsletter）\n"
  open_url "MkSaaS Newsletter 文档" "https://mksaas.com/docs/newsletter"
  open_url "MkSaaS 环境变量（邮件订阅）" "https://mksaas.com/zh/docs/env#%E9%82%AE%E4%BB%B6%E8%AE%A2%E9%98%85"

  local provider_choice
  provider_choice="$(choose_option "选择 Newsletter 服务商：" "1" \
    "Resend" \
    "Beehiiv" \
    "跳过")"

  case "$provider_choice" in
    Resend)
      open_url "Resend 控制台" "https://resend.com/"
      open_url "Resend API Keys" "https://resend.com/api-keys"
      cat <<'EOF'
申请步骤（Resend）：
1. 在 Resend 的 API Keys 创建 API Key。
2. 将 API Key 填入 RESEND_API_KEY。
EOF
      local current_key
      current_key="$(read_profile_env_kv "$project_dir" "$profile" "RESEND_API_KEY")"
      if [[ -z "$current_key" && -f "$env_file" ]]; then
        current_key="$(read_env_kv "$env_file" "RESEND_API_KEY")"
      fi
      local api_key=""
      prompt_input "RESEND_API_KEY" api_key "$current_key" "true"
      upsert_profile_env_kv "$project_dir" "$profile" "RESEND_API_KEY" "$api_key"
      upsert_project_meta_kv "$project_dir" "NEWSLETTER_PROVIDER" "resend"
      upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_NEWSLETTER_PROVIDER" "resend"
      ;;
    Beehiiv)
      open_url "Beehiiv 控制台" "https://beehiiv.com/"
      cat <<'EOF'
申请步骤（Beehiiv）：
1. 在 Beehiiv 后台进入 Settings -> API，生成 API Key。
2. 获取 Publication ID（可以从 URL 或设置页面找到）。
3. 填入 BEEHIIV_API_KEY 与 BEEHIIV_PUBLICATION_ID。
EOF
      local current_api_key
      local current_pub_id
      current_api_key="$(read_profile_env_kv "$project_dir" "$profile" "BEEHIIV_API_KEY")"
      current_pub_id="$(read_profile_env_kv "$project_dir" "$profile" "BEEHIIV_PUBLICATION_ID")"
      if [[ -z "$current_api_key" && -f "$env_file" ]]; then
        current_api_key="$(read_env_kv "$env_file" "BEEHIIV_API_KEY")"
      fi
      if [[ -z "$current_pub_id" && -f "$env_file" ]]; then
        current_pub_id="$(read_env_kv "$env_file" "BEEHIIV_PUBLICATION_ID")"
      fi
      local beehiiv_api_key=""
      local beehiiv_publication_id=""
      prompt_input "BEEHIIV_API_KEY" beehiiv_api_key "$current_api_key" "true"
      prompt_input "BEEHIIV_PUBLICATION_ID" beehiiv_publication_id "$current_pub_id"
      upsert_profile_env_kv "$project_dir" "$profile" "BEEHIIV_API_KEY" "$beehiiv_api_key"
      upsert_profile_env_kv "$project_dir" "$profile" "BEEHIIV_PUBLICATION_ID" "$beehiiv_publication_id"
      upsert_project_meta_kv "$project_dir" "NEWSLETTER_PROVIDER" "beehiiv"
      upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_NEWSLETTER_PROVIDER" "beehiiv"
      ;;
    跳过)
      printf "已跳过 Newsletter 配置\n"
      return 0
      ;;
    *)
      err "未知选择"
      exit 1
      ;;
  esac

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
  configure_newsletter "$profile" "$project_dir"
}

main "$@"
