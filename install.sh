#!/usr/bin/env bash
# Instala o agy-turbo: statusline + plugins. Uso: ./install.sh [statusline] [prismantis] (padrão: tudo)
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
command -v agy >/dev/null || { echo "agy não encontrado no PATH" >&2; exit 1; }
command -v jq  >/dev/null || { echo "precisa de jq" >&2; exit 1; }
parts=("$@"); [ ${#parts[@]} -eq 0 ] && parts=(statusline $(ls "$DIR/plugins"))
for p in "${parts[@]}"; do
  case "$p" in
    statusline) "$DIR/statusline/install.sh" ;;
    *) [ -d "$DIR/plugins/$p" ] || { echo "parte desconhecida: $p" >&2; exit 1; }
       agy plugin install "$DIR/plugins/$p" ;;
  esac
done
echo "Pronto. Abra um agy novo."
