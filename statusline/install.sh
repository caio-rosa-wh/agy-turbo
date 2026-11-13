#!/usr/bin/env bash
# Instala o agy-cockpit como statusLine do agy. Guarda a configuração anterior para o uninstall.sh.
set -euo pipefail
command -v jq >/dev/null || { echo "precisa de jq" >&2; exit 1; }
DIR=$(cd "$(dirname "$0")" && pwd)
CFG=${AGY_SETTINGS:-$HOME/.gemini/antigravity-cli/settings.json}
PREV=$(dirname "$CFG")/agy-cockpit.previous.json
chmod +x "$DIR/statusline.sh"
[ -f "$CFG" ] || echo '{}' > "$CFG"
jq empty "$CFG" || { echo "settings.json inválido, não mexi: $CFG" >&2; exit 1; }
cp -p "$CFG" "$CFG.agy-cockpit.bak.$(date +%Y%m%d-%H%M%S)"
# Guarda o statusLine anterior só na primeira instalação (reinstalar não sobrescreve).
if [ ! -f "$PREV" ]; then jq '{statusLine: (.statusLine // null)}' "$CFG" > "$PREV"; fi
tmp=$(mktemp "$CFG.XXXX")
jq --arg cmd "$DIR/statusline.sh" --argjson stack "${COCKPIT_STACK:-false}" \
  '.statusLine = {type: "command", command: $cmd, stack_with_default: $stack}' "$CFG" > "$tmp"
chmod --reference="$CFG" "$tmp"; mv "$tmp" "$CFG"
echo "agy-cockpit instalado em $CFG"
echo "statusLine anterior guardado em $PREV (use uninstall.sh para voltar)"
echo "Abra um agy novo para ver."
