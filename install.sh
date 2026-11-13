#!/usr/bin/env bash
# Instala o agy-turbo a partir desta pasta (o mesmo que: agy plugin install https://github.com/caio-rosa-wh/agy-turbo).
# O plugin se configura sozinho na primeira sessão do agy; aqui já rodamos essa configuração na hora.
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
command -v agy >/dev/null || { echo "agy não encontrado no PATH" >&2; exit 1; }
agy plugin install "$DIR"
ROOT=$HOME/.gemini/config/plugins/agy-turbo
[ -d "$ROOT" ] || ROOT=$DIR
PLUGIN_ROOT=$ROOT PLUGIN_DATA=${AGY_TURBO_DATA:-$HOME/.gemini/antigravity-cli/plugin_data/agy-turbo} \
  python3 -I "$ROOT/hooks/bootstrap.py"
cat "${AGY_TURBO_DATA:-$HOME/.gemini/antigravity-cli/plugin_data/agy-turbo}/bootstrap.log" | tail -8
echo "Pronto. Abra um terminal novo e rode: agy"
