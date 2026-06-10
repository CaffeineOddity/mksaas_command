#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：配置支付通知（Discord/飞书 Webhook），写入环境变量
# 参数：$1 [profile], $2 [project_dir]
# 返回：无
##
configure_notification() {
  local profile="$1"
  local project_dir="$2"

  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  printf "\n配置通知（支付成功提醒）\n"
  open_url "MkSaaS Notification 文档" "https://mksaas.com/docs/notification"
  open_url "MkSaaS 环境变量（通知）" "https://mksaas.com/zh/docs/env#%E9%80%9A%E7%9F%A5"

  local provider_choice
  provider_choice="$(choose_option "选择通知渠道：" "1" \
    "Discord" \
    "飞书" \
    "跳过")"

  case "$provider_choice" in
    Discord)
      open_url "Discord" "https://discord.com/"
      cat <<'EOF'
申请步骤（Discord Webhook）：
1. 在你的 Discord Server 里选择一个频道，进入 Channel Settings。
2. Integrations -> Webhooks -> New Webhook。
3. 复制 Webhook URL，填入 DISCORD_WEBHOOK_URL。
EOF
      local webhook=""
      prompt_input "DISCORD_WEBHOOK_URL" webhook "$(read_profile_env_kv "$project_dir" "$profile" "DISCORD_WEBHOOK_URL")" "true"
      upsert_profile_env_kv "$project_dir" "$profile" "DISCORD_WEBHOOK_URL" "$webhook"
      upsert_project_meta_kv "$project_dir" "NOTIFICATION_PROVIDER" "discord"
      upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_NOTIFICATION_PROVIDER" "discord"
      ;;
    飞书)
      open_url "飞书开放平台" "https://open.feishu.cn/"
      cat <<'EOF'
申请步骤（飞书 Webhook）：
1. 在飞书群聊里打开群设置 -> 机器人管理。
2. 添加自定义机器人并启用 Webhook。
3. 复制 Webhook URL，填入 FEISHU_WEBHOOK_URL。
EOF
      local webhook=""
      prompt_input "FEISHU_WEBHOOK_URL" webhook "$(read_profile_env_kv "$project_dir" "$profile" "FEISHU_WEBHOOK_URL")" "true"
      upsert_profile_env_kv "$project_dir" "$profile" "FEISHU_WEBHOOK_URL" "$webhook"
      upsert_project_meta_kv "$project_dir" "NOTIFICATION_PROVIDER" "feishu"
      upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_NOTIFICATION_PROVIDER" "feishu"
      ;;
    跳过)
      printf "已跳过通知配置\n"
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
  configure_notification "$profile" "$project_dir"
}

main "$@"
