#!/usr/bin/env bash
# Remove o agy-turbo. Uso: ./uninstall.sh [statusline] [prismantis] (padrão: tudo)
set -uo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
parts=("$@"); [ ${#parts[@]} -eq 0 ] && parts=(statusline $(ls "$DIR/plugins"))
for p in "${parts[@]}"; do
  case "$p" in
    statusline) "$DIR/statusline/uninstall.sh" ;;
    *) agy plugin uninstall "$p" ;;
  esac
done
