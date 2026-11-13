#!/usr/bin/env bash
# Função agy: roteamento e caminho "sem tmux" (oferece setup uma vez, depois cai no agy puro).
DIR=$(cd "$(dirname "$0")/.." && pwd); T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/home" "$T/sys"
for u in bash sh find mkdir touch dirname cat tr; do ln -s "$(command -v $u)" "$T/sys/$u"; done   # PATH sem tmux
printf '#!/bin/sh\necho "BIN $*"\n' > "$T/bin/agy"
printf '#!/bin/sh\necho "TURBO $*"\n' > "$T/bin/agy-turbo"
printf '#!/bin/sh\necho SETUP; exit 1\n' > "$T/bin/agy-turbo-setup"
chmod +x "$T/bin/"*
SCRIPT=$(command -v script)
run() { HOME=$T/home PATH=$T/bin:$T/sys "$SCRIPT" -qc "$T/sys/bash --norc -c '. $DIR/shell/agy.bash; $1'" /dev/null | tr -d '\r'; }
fail=0
[ "$(run 'agy -p oi')" = "BIN -p oi" ] || { echo "FAIL -p"; fail=1; }
[ "$(run 'agy plugin list')" = "BIN plugin list" ] || { echo "FAIL subcomando"; fail=1; }
o=$(run 'agy'); [ "$o" = $'SETUP\nBIN ' ] || { echo "FAIL sem tmux 1ª vez: $o"; fail=1; }
o=$(run 'agy'); [ "$o" = "BIN " ] || { echo "FAIL sem tmux 2ª vez (não deve perguntar de novo): $o"; fail=1; }
ln -s "$(command -v tmux || echo /bin/true)" "$T/bin/tmux"
[ "$(run 'agy --model x')" = "TURBO --model x" ] || { echo "FAIL com tmux"; fail=1; }
rm -f "$T/home/.local/share/agy-turbo/.setup-asked"
o=$(run 'agy --model x'); [ "$o" = $'SETUP\nTURBO --model x' ] || { echo "FAIL sem venv 1ª vez: $o"; fail=1; }
exit $fail
