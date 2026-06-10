#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：配置统计分析（Analytics）环境变量
# 参数：$1 [profile], $2 [project_dir]
# 返回：无
##
configure_analytics() {
  local profile="$1"
  local project_dir="$2"

  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  printf "\n配置统计分析（Analytics）\n"
  open_url "MkSaaS Analytics 文档" "https://mksaas.com/docs/analytics"
  open_url "MkSaaS 环境变量（统计分析）" "https://mksaas.com/zh/docs/env#%E7%BB%9F%E8%AE%A1%E5%88%86%E6%9E%90"

  local provider
  provider="$(choose_option "选择 Analytics 服务商：" "1" \
    "Google Analytics" \
    "Umami" \
    "Plausible" \
    "PostHog" \
    "DataFast" \
    "Ahrefs" \
    "OpenPanel" \
    "Clarity" \
    "Seline" \
    "跳过")"

  local input=""
  case "$provider" in
    "Google Analytics")
      open_url "Google Analytics" "https://analytics.google.com/"
      cat <<'EOF'
申请步骤：
1. 在 Google Analytics 创建一个 Property。
2. 获取 Measurement ID（以 G- 开头）。
3. 填入 NEXT_PUBLIC_GOOGLE_ANALYTICS_ID。
EOF
      prompt_input "NEXT_PUBLIC_GOOGLE_ANALYTICS_ID（G-...）" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_GOOGLE_ANALYTICS_ID")"
      upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_GOOGLE_ANALYTICS_ID" "$input"
      upsert_project_meta_kv "$project_dir" "ANALYTICS_PROVIDER" "google"
      upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_ANALYTICS_PROVIDER" "google"
      ;;
    Umami)
      open_url "Umami" "https://umami.is/"
      cat <<'EOF'
申请步骤：
1. 在 Umami 创建一个 Website，复制 Website ID。
2. 脚本 URL 默认可用 https://cloud.umami.is/script.js（自建则填你自己的地址）。
EOF
      prompt_input "NEXT_PUBLIC_UMAMI_WEBSITE_ID" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_UMAMI_WEBSITE_ID")"
      upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_UMAMI_WEBSITE_ID" "$input"
      prompt_input "NEXT_PUBLIC_UMAMI_SCRIPT" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_UMAMI_SCRIPT")"
      if [[ -z "$input" ]]; then
        input="https://cloud.umami.is/script.js"
      fi
      upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_UMAMI_SCRIPT" "$input"
      upsert_project_meta_kv "$project_dir" "ANALYTICS_PROVIDER" "umami"
      upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_ANALYTICS_PROVIDER" "umami"
      ;;
    Plausible)
      open_url "Plausible" "https://plausible.io/"
      cat <<'EOF'
申请步骤：
1. 在 Plausible 添加网站域名。
2. 填入域名到 NEXT_PUBLIC_PLAUSIBLE_DOMAIN。
3. 脚本 URL 默认 https://plausible.io/js/script.js（自建则填你自己的地址）。
EOF
      prompt_input "NEXT_PUBLIC_PLAUSIBLE_DOMAIN" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_PLAUSIBLE_DOMAIN")"
      upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_PLAUSIBLE_DOMAIN" "$input"
      prompt_input "NEXT_PUBLIC_PLAUSIBLE_SCRIPT" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_PLAUSIBLE_SCRIPT")"
      if [[ -z "$input" ]]; then
        input="https://plausible.io/js/script.js"
      fi
      upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_PLAUSIBLE_SCRIPT" "$input"
      upsert_project_meta_kv "$project_dir" "ANALYTICS_PROVIDER" "plausible"
      upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_ANALYTICS_PROVIDER" "plausible"
      ;;
    PostHog)
      open_url "PostHog" "https://posthog.com/"
      cat <<'EOF'
申请步骤：
1. 在 PostHog 创建 Project，复制 Project API Key。
2. Host 通常是 https://app.posthog.com（自建则填你自己的 host）。
EOF
      prompt_input "NEXT_PUBLIC_POSTHOG_KEY" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_POSTHOG_KEY")"
      upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_POSTHOG_KEY" "$input"
      prompt_input "NEXT_PUBLIC_POSTHOG_HOST" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_POSTHOG_HOST")"
      if [[ -z "$input" ]]; then
        input="https://app.posthog.com"
      fi
      upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_POSTHOG_HOST" "$input"
      upsert_project_meta_kv "$project_dir" "ANALYTICS_PROVIDER" "posthog"
      upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_ANALYTICS_PROVIDER" "posthog"
      ;;
    DataFast)
      open_url "DataFast" "https://datafa.st/"
      cat <<'EOF'
申请步骤：
1. 在 DataFast 添加网站，获取 Website ID 和 Domain。
2. 填入 NEXT_PUBLIC_DATAFAST_WEBSITE_ID 与 NEXT_PUBLIC_DATAFAST_DOMAIN。
EOF
      prompt_input "NEXT_PUBLIC_DATAFAST_WEBSITE_ID" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_DATAFAST_WEBSITE_ID")"
      upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_DATAFAST_WEBSITE_ID" "$input"
      prompt_input "NEXT_PUBLIC_DATAFAST_DOMAIN" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_DATAFAST_DOMAIN")"
      upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_DATAFAST_DOMAIN" "$input"
      upsert_project_meta_kv "$project_dir" "ANALYTICS_PROVIDER" "datafast"
      upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_ANALYTICS_PROVIDER" "datafast"
      ;;
    Ahrefs)
      open_url "Ahrefs" "https://ahrefs.com/"
      open_url "Ahrefs Web Analytics" "https://app.ahrefs.com/dashboard?tab=webAnalytics"
      cat <<'EOF'
申请步骤：
1. 在 Ahrefs Web Analytics 创建网站，获取 Website ID。
2. 填入 NEXT_PUBLIC_AHREFS_WEBSITE_ID。
EOF
      prompt_input "NEXT_PUBLIC_AHREFS_WEBSITE_ID" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_AHREFS_WEBSITE_ID")"
      upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_AHREFS_WEBSITE_ID" "$input"
      upsert_project_meta_kv "$project_dir" "ANALYTICS_PROVIDER" "ahrefs"
      upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_ANALYTICS_PROVIDER" "ahrefs"
      ;;
    OpenPanel)
      open_url "OpenPanel" "https://openpanel.dev/"
      cat <<'EOF'
申请步骤：
1. 在 OpenPanel 创建 Project，获取 Client ID。
2. 填入 NEXT_PUBLIC_OPENPANEL_CLIENT_ID。
EOF
      prompt_input "NEXT_PUBLIC_OPENPANEL_CLIENT_ID" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_OPENPANEL_CLIENT_ID")"
      upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_OPENPANEL_CLIENT_ID" "$input"
      upsert_project_meta_kv "$project_dir" "ANALYTICS_PROVIDER" "openpanel"
      upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_ANALYTICS_PROVIDER" "openpanel"
      ;;
    Clarity)
      open_url "Microsoft Clarity" "https://clarity.microsoft.com/"
      cat <<'EOF'
申请步骤：
1. 在 Clarity 创建 Project，获取 Project ID。
2. 填入 NEXT_PUBLIC_CLARITY_PROJECT_ID。
EOF
      prompt_input "NEXT_PUBLIC_CLARITY_PROJECT_ID" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_CLARITY_PROJECT_ID")"
      upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_CLARITY_PROJECT_ID" "$input"
      upsert_project_meta_kv "$project_dir" "ANALYTICS_PROVIDER" "clarity"
      upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_ANALYTICS_PROVIDER" "clarity"
      ;;
    Seline)
      open_url "Seline" "https://seline.com/"
      cat <<'EOF'
申请步骤：
1. 在 Seline 创建项目，获取 Token。
2. 填入 NEXT_PUBLIC_SELINE_TOKEN。
EOF
      prompt_input "NEXT_PUBLIC_SELINE_TOKEN" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_SELINE_TOKEN")" "true"
      upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_SELINE_TOKEN" "$input"
      upsert_project_meta_kv "$project_dir" "ANALYTICS_PROVIDER" "seline"
      upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_ANALYTICS_PROVIDER" "seline"
      ;;
    跳过)
      printf "已跳过 Analytics 配置\n"
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
  configure_analytics "$profile" "$project_dir"
}

main "$@"
