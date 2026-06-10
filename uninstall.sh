#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

##
# 功能：打印错误并退出
# 参数：$1 message
# 返回：无
##
err() {
  printf "错误: %s\n" "$1" >&2
}

##
# 功能：交互读取输入
# 参数：$1 prompt, $2 var_name, $3 default_value
# 返回：通过引用变量写回
##
prompt_input() {
  local prompt="$1"
  local var_name="$2"
  local default_value="$3"

  local input=""
  if [[ -n "$default_value" ]]; then
    read -r -p "$prompt (默认: $default_value): " input
    if [[ -z "$input" ]]; then
      input="$default_value"
    fi
  else
    read -r -p "$prompt: " input
  fi

  printf -v "$var_name" "%s" "$input"
}

main() {
  local cmd_name_default="mksaas"
  local cmd_name=""
  prompt_input "要卸载的命令名" cmd_name "$cmd_name_default"
  if [[ -z "$cmd_name" ]]; then
    err "命令名不能为空"
    exit 1
  fi

  local bin_dir_default="${HOME}/.local/bin"
  local bin_dir=""
  prompt_input "命令所在 bin 目录" bin_dir "$bin_dir_default"
  if [[ -z "$bin_dir" ]]; then
    err "bin 目录不能为空"
    exit 1
  fi

  local link_path="${bin_dir}/${cmd_name}"
  if [[ ! -e "$link_path" ]]; then
    err "未找到：$link_path"
    exit 1
  fi

  local confirm=""
  prompt_input "确认删除该命令？输入 yes 继续" confirm "yes"
  if [[ "$confirm" != "yes" ]]; then
    err "已取消"
    exit 1
  fi

  rm -f "$link_path"
  printf "已删除：%s\n" "$link_path"
}

main "$@"
