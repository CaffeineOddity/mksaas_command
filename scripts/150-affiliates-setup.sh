#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：配置联盟营销（Affiliates）环境变量
# 参数：$1 [profile], $2 [project_dir]
# 返回：无
##
configure_affiliates() {
  local profile="$1"
  local project_dir="$2"

  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true

  printf "\n配置联盟营销（Affiliates）\n"
  open_url "MkSaaS Affiliates 文档" "https://mksaas.com/docs/affiliates"
  open_url "MkSaaS 环境变量（联盟营销）" "https://mksaas.com/zh/docs/env#%E8%81%94%E7%9B%9F%E8%90%A5%E9%94%80"

  local provider
  provider="$(choose_option "选择联盟营销平台：" "1" \
    "Affonso" \
    "PromoteKit" \
    "两者都用" \
    "跳过")"

  local input=""
  case "$provider" in
    Affonso)
      open_url "Affonso" "https://affonso.io/?atp=javayhu"
      cat <<'EOF'
申请步骤（Affonso）：
1. 注册并创建 Affiliate Program。
2. 在后台找到你的 Program ID。
3. 填入 NEXT_PUBLIC_AFFILIATE_AFFONSO_ID。
EOF
      prompt_input "NEXT_PUBLIC_AFFILIATE_AFFONSO_ID" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_AFFILIATE_AFFONSO_ID")"
      upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_AFFILIATE_AFFONSO_ID" "$input"
      upsert_project_meta_kv "$project_dir" "AFFILIATES_PROVIDER" "affonso"
      upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_AFFILIATES_PROVIDER" "affonso"
      ;;
    PromoteKit)
      open_url "PromoteKit" "https://www.promotekit.com/?via=javayhu"
      cat <<'EOF'
申请步骤（PromoteKit）：
1. 注册并创建 Affiliate Program。
2. 复制 Program ID。
3. 填入 NEXT_PUBLIC_AFFILIATE_PROMOTEKIT_ID。
EOF
      prompt_input "NEXT_PUBLIC_AFFILIATE_PROMOTEKIT_ID" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_AFFILIATE_PROMOTEKIT_ID")"
      upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_AFFILIATE_PROMOTEKIT_ID" "$input"
      upsert_project_meta_kv "$project_dir" "AFFILIATES_PROVIDER" "promotekit"
      upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_AFFILIATES_PROVIDER" "promotekit"
      ;;
    两者都用)
      open_url "Affonso" "https://affonso.io/?atp=javayhu"
      open_url "PromoteKit" "https://www.promotekit.com/?via=javayhu"
      cat <<'EOF'
申请步骤：
1. 分别在 Affonso / PromoteKit 创建 Program，并拿到各自的 Program ID。
2. 将两个 ID 都写入环境变量。
EOF
      prompt_input "NEXT_PUBLIC_AFFILIATE_AFFONSO_ID" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_AFFILIATE_AFFONSO_ID")"
      upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_AFFILIATE_AFFONSO_ID" "$input"
      prompt_input "NEXT_PUBLIC_AFFILIATE_PROMOTEKIT_ID" input "$(read_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_AFFILIATE_PROMOTEKIT_ID")"
      upsert_profile_env_kv "$project_dir" "$profile" "NEXT_PUBLIC_AFFILIATE_PROMOTEKIT_ID" "$input"
      upsert_project_meta_kv "$project_dir" "AFFILIATES_PROVIDER" "both"
      upsert_project_meta_kv "$project_dir" "$(profile_prefix "$profile")_AFFILIATES_PROVIDER" "both"
      ;;
    跳过)
      printf "已跳过 Affiliates 配置\n"
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
  configure_affiliates "$profile" "$project_dir"
}

main "$@"
