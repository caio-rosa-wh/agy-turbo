#!/usr/bin/env bash
# Volta o statusLine que existia antes do install.sh.
set -euo pipefail
CFG=${AGY_SETTINGS:-$HOME/.gemini/antigravity-cli/settings.json}
PREV=$(dirname "$CFG")/agy-cockpit.previous.json
[ -f "$PREV" ] || { echo "nada a restaurar ($PREV não existe)" >&2; exit 1; }
cp -p "$CFG" "$CFG.agy-cockpit.bak.$(date +%Y%m%d-%H%M%S)"
tmp=$(mktemp "$CFG.XXXX")
jq --slurpfile p "$PREV" 'if $p[0].statusLine == null then del(.statusLine) else .statusLine = $p[0].statusLine end' "$CFG" > "$tmp"
chmod --reference="$CFG" "$tmp"; mv "$tmp" "$CFG"; rm -f "$PREV"
echo "statusLine anterior restaurado em $CFG"
