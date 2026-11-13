#!/usr/bin/env bash
# Testes offline: statusline com payload real e casos de borda, instalador numa cópia do settings, validate dos plugins.
set -u
DIR=$(cd "$(dirname "$0")/.." && pwd); SL=$DIR/statusline/statusline.sh
FIX=$DIR/docs/evidencias/statusline-stdin-agy-1.5.7.json
fail=0; ok() { echo "ok   $1"; }; ko() { echo "FAIL $1"; fail=1; }
strip() { sed -E 's/\x1b\[[0-9;]*m//g'; }

out=$(jq '.context_window.total_input_tokens=158000|.context_window.used_percentage=16|.cost=2.48|.terminal_width=110|.quota["gemini-5h"].remaining_fraction=0.74|.quota["gemini-weekly"].remaining_fraction=0.55' "$FIX" | "$SL" | strip)
l1=$(sed -n 1p <<<"$out"); l2=$(sed -n 2p <<<"$out")
[[ $l1 == *"Gemini 4 Hydrogen "* && $l1 != *"(High)"* ]] && ok "modelo sem sufixo" || ko "modelo: $l1"
[[ $l1 == *"| high"* ]] && ok "esforço" || ko "esforço: $l1"
[[ $l1 == *"tok 158k/1M (16%)"* ]] && ok "tokens compactos com ponto" || ko "tokens: $l1"
[[ $l1 == *'$2.48'* ]] && ok "custo" || ko "custo: $l1"
[[ $l2 == *"5h"*"26%"*"7d"*"45%"* ]] && ok "cotas gemini" || ko "cotas: $l2"
out=$(jq '.model.display_name="Claude Sonnet 5.5 (Thinking)"|.quota["3p-5h"].remaining_fraction=0.1' "$FIX" | "$SL" | strip)
[[ $(sed -n 2p <<<"$out") == *" 90%"* ]] && ok "cota 3p para Claude" || ko "3p: $out"
[[ $(echo '{}' | "$SL" | strip) == *"tok 0/0"* ]] && ok "JSON vazio" || ko "JSON vazio"
[[ $(echo 'xx' | "$SL") == *"JSON inválido"* ]] && ok "JSON inválido" || ko "JSON inválido"
[[ $(jq '.terminal_width=60' "$FIX" | NO_COLOR=1 "$SL") != *$'\033'* ]] && ok "NO_COLOR" || ko "NO_COLOR"

CH=$DIR/skills/chart/scripts/chart.py
o=$(python3 "$CH" func --expr "cos(x)" --from 0 --to 2*pi --width 50); [[ $o == *"π/2"*"3π/2"*"2π"* && $o == *"-1 ┤"* ]] && ok "chart func cos" || ko "chart func"
o=$(python3 "$CH" bar --labels a,b,c --values 3,-2,5); [[ $o == *"-2"* && $o == *"█"* ]] && ok "chart bar com negativo" || ko "chart bar"
o=$(python3 "$CH" line --series "a:1,2,3" --series "b:3,2,1"); [[ $o == *"● a"*"○ b"* ]] && ok "chart line com legenda" || ko "chart line"
python3 "$CH" func --expr "__import__('os')" >/dev/null 2>&1 && ko "chart bloqueia expressão" || ok "chart bloqueia expressão"
w=$(python3 "$CH" func --expr "sin(x)" --width 60 | python3 -Ic 'import sys; print(max(len(l.rstrip("\n")) for l in sys.stdin))'); [ "$w" -le 74 ] && ok "chart cabe em 74 colunas" || ko "chart largura $w"

CO=$DIR/hooks/collect.py; TD=$(mktemp -d)
jq -c '.' "$DIR/docs/evidencias/posttooluse-agy-1.5.7.jsonl" | sed "s#/caminho/do/projeto#$TD#g" | while read -r l; do printf '%s' "$l" | PLUGIN_DATA=$TD python3 -I "$CO" >/dev/null; done
touch "$TD/capture_hook.py"
[[ $(jq -r 'select(.tool=="read_file") | .kind' "$TD/activity.jsonl") == read ]] && ok "coletor: read_file" || ko "coletor read_file"
[[ $(jq -r 'select(.tool=="edit_file") | .kind' "$TD/activity.jsonl") == write ]] && ok "coletor: edit_file" || ko "coletor edit_file"
[[ $(echo 'lixo' | PLUGIN_DATA=$TD python3 -I "$CO") == "{}" ]] && ok "coletor: entrada inválida responde {}" || ko "coletor inválido"
echo "{\"toolCall\":{\"name\":\"run_command\",\"args\":{\"CommandLine\":\"rm sumiu.txt\"}},\"cwd\":\"$TD\"}" | PLUGIN_DATA=$TD python3 -I "$CO" >/dev/null
tail -2 "$TD/activity.jsonl" | grep -q '"kind": "write".*sumiu.txt' && ok "coletor: rm de arquivo já apagado" || ko "coletor rm"
rm -rf "$TD"
VPY=${AGY_TURBO_VENV:-$HOME/.local/share/agy-turbo/venv}/bin/python
if [ -x "$VPY" ]; then
  [[ $("$VPY" "$DIR/tests/filetree/render_test.py" "$DIR/filetree" 2>&1 | tail -1) == ok ]] && ok "agy-tree headless" || ko "agy-tree headless"
else echo "skip agy-tree (venv ausente)"; fi

python3 -I "$DIR/tests/effortless_test.py" "$DIR" && ok "effortless: decisões e aplicação via tmux" || ko "effortless"
python3 -I "$DIR/tests/bootstrap_test.py" "$DIR" && ok "bootstrap: HOME limpo, idempotente" || ko "bootstrap"
"$DIR/tests/shell_test.sh" && ok "função agy: roteamento e oferta de setup sem tmux" || ko "função agy"
grep -nE "[\"']jq[\"']|(^|[|;&] *)jq " "$DIR/statusline/"* $(ls "$DIR"/hooks/*.py | grep -v collect.py) "$DIR/bin/"* "$DIR/shell/"* && ko "runtime ainda usa jq" || ok "runtime sem jq"
TD=$(mktemp -d); echo '{"hint":"compact","pending":"low","reason":"só mostrar"}' > "$TD/effortless.json"
o=$(jq '.terminal_width=150|.context_window.used_percentage=85' "$FIX" | AGY_TURBO_DATA=$TD "$SL" | strip | sed -n 3p); rm -rf "$TD"
[[ $o == *"85% context"*"[ high ]"*"auto: só mostrar"*"depois desta resposta → low"*"contexto cheio: /compact"* ]] && ok "statusline: linha do effortless" || ko "statusline effortless: $o"

if command -v agy >/dev/null; then
  agy plugin validate "$DIR" --strict >/dev/null 2>&1 && ok "validate agy-turbo" || ko "validate agy-turbo"
else echo "skip validate (agy ausente)"; fi
exit $fail
