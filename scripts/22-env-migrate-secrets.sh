#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

##
# 功能：将历史遗留写入 project.yaml 的敏感变量迁移到 secrets.<profile>.env，并从 project.yaml 移除
# 参数：$1 [project_dir]
# 返回：无
##
migrate_secrets_from_project_yaml() {
  local project_dir="$1"
  require_project_meta "$project_dir"

  local meta_file
  meta_file="$(get_project_meta_file "$project_dir")"
  if [[ ! -f "$meta_file" ]]; then
    err "未找到项目配置文件：$meta_file"
    exit 1
  fi

  local tmp_keys
  tmp_keys="$(mktemp)"

  local migrated_count=0
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue

    local yaml_key="${line%%:*}"
    local rest="${line#*:}"
    rest="${rest# }"
    rest="${rest%\"}"
    rest="${rest#\"}"
    rest="${rest//\\\"/\"}"
    rest="${rest//\\\\/\\}"

    local profile=""
    local key=""
    if [[ "$yaml_key" == TEST_ENV_* ]]; then
      profile="test"
      key="${yaml_key#TEST_ENV_}"
    elif [[ "$yaml_key" == PROD_ENV_* ]]; then
      profile="prod"
      key="${yaml_key#PROD_ENV_}"
    else
      continue
    fi

    if ! is_sensitive_env_key "$key"; then
      continue
    fi

    upsert_profile_secret_env_kv "$project_dir" "$profile" "$key" "$rest"
    printf "%s\n" "$yaml_key" >> "$tmp_keys"
    migrated_count=$((migrated_count + 1))
  done < <(grep -E '^(TEST_ENV_|PROD_ENV_)' "$meta_file" || true)

  if [[ "$migrated_count" -eq 0 ]]; then
    rm -f "$tmp_keys" || true
    printf "未发现需要迁移的敏感变量（project.yaml 中没有敏感的 TEST_ENV_/PROD_ENV_ 键）。\n"
    return 0
  fi

  local tmp_meta="${meta_file}.tmp.$$"
  awk 'NR==FNR { keys[$0]=1; next }
       { k=$0; sub(":.*", "", k); if (k in keys) next; print }' "$tmp_keys" "$meta_file" > "$tmp_meta"
  mv "$tmp_meta" "$meta_file"
  rm -f "$tmp_keys" || true

  "${SCRIPT_DIR}/20-prepare-env.sh" "$project_dir" >/dev/null 2>&1 || true
  printf "已迁移 %d 个敏感变量到 secrets.*.env，并已重新生成 .env.test/.env.prod\n" "$migrated_count"
}

main() {
  if [[ $# -gt 1 ]]; then
    err "用法: $0 [project_dir]"
    exit 1
  fi

  local project_dir
  project_dir="$(resolve_existing_project_dir "${1:-}")"
  migrate_secrets_from_project_yaml "$project_dir"
}

main "$@"

