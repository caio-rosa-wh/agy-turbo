#!/usr/bin/env bash
# agy-cockpit: statusline de 2 linhas para o Antigravity CLI (agy).
# Inspirada no visual do "Cockpit" (statusline.sh/community/cockpit-4shq); implementação própria.
#
# Linha 1: modelo | esforço   tok usado/total (pct) barra   custo
# Linha 2: usage   5h barra pct   7d barra pct   (mesmo layout do Cockpit no Claude Code)
#
# Lê o JSON que o agy manda no stdin. Precisa de bash e jq.
# Variáveis opcionais:
#   COCKPIT_BAR=30        largura das barras (padrão: ajusta a terminal_width)
#   COCKPIT_QUOTA=auto    auto | gemini | 3p  (qual grupo de cota mostrar)
#   COCKPIT_ASCII=1       barras com # e . em vez de glifos
#   COCKPIT_RESET=1       mostra em quanto tempo cada cota renova (↻4h00m)
#   COCKPIT_STATE=1       mostra o estado do agente (running, initializing...)
#   NO_COLOR=1            sem cores

set -u
command -v jq >/dev/null 2>&1 || { printf 'agy-cockpit: instale jq\n'; exit 0; }

input=$(cat)

# Uma única chamada jq: devolve os campos separados por TAB.
IFS=$'\t' read -r model effort used total pct cost width q5 r5 qw rw state < <(
  printf '%s' "$input" | jq -r --arg pref "${COCKPIT_QUOTA:-auto}" '
    def num: if type == "number" then . elif type == "string" then (tonumber? // null) else null end;
    (.model.display_name // .model.id // "?") as $name
    | ($name | sub("\\s*\\([^)]*\\)\\s*$"; "")) as $short
    | (.model.effort // "") as $eff
    | (if $pref == "auto" then
         (if (($name + " " + (.model.id // "")) | test("claude|gpt|sonnet|opus|haiku"; "i")) then "3p" else "gemini" end)
       else $pref end) as $grp
    | (.quota // {}) as $q
    | ($q[$grp + "-5h"] // ($q | to_entries | map(select(.key | endswith("-5h"))) | .[0].value) // {}) as $b5
    | ($q[$grp + "-weekly"] // ($q | to_entries | map(select(.key | endswith("-weekly"))) | .[0].value) // {}) as $bw
    | def usedpct($b): if ($b.remaining_fraction | num) == null then "" else ((1 - ($b.remaining_fraction | num)) * 100 | round | tostring) end;
      [ $short,
        $eff,
        ((.context_window.total_input_tokens | num) // 0 | tostring),
        ((.context_window.context_window_size | num) // 0 | tostring),
        ((.context_window.used_percentage | num) // 0 | round | tostring),
        ((.cost | if type == "object" then (.total_cost_usd // .estimated_cost_usd) else . end | num) // "" | tostring),
        ((.terminal_width | num) // 0 | tostring),
        usedpct($b5), (($b5.reset_in_seconds | num) // "" | tostring),
        usedpct($bw), (($bw.reset_in_seconds | num) // "" | tostring),
        (.agent_state // "")
      ] | map(if . == "" then "-" else . end) | @tsv
  ' 2>/dev/null
)

[ -n "${model:-}" ] || { printf 'agy-cockpit: JSON inválido\n'; exit 0; }
unset_dash() { [ "$1" = "-" ] && printf '' || printf '%s' "$1"; }
effort=$(unset_dash "$effort"); cost=$(unset_dash "$cost")
q5=$(unset_dash "$q5"); r5=$(unset_dash "$r5"); qw=$(unset_dash "$qw"); rw=$(unset_dash "$rw")
state=$(unset_dash "$state")

# ---------- cores ----------
if [ -n "${NO_COLOR:-}" ]; then
  c() { :; }; R=''
else
  c() { printf '\033[%sm' "$1"; }; R=$'\033[0m'
fi
PILL='1;38;2;255;255;255;48;2;43;47;58'
CTX='38;2;143;184;218'
FIVE='38;2;156;192;159'
WEEK='38;2;216;184;112'
WARN='38;2;232;125;110'
DIM='2'

# ---------- helpers ----------
compact() { # 94400 -> 94.4k, 1048576 -> 1M
  LC_ALL=C awk -v n="$1" 'BEGIN{
    if (n < 1000) { printf "%d", n; exit }
    if (n < 1000000) { v = n/1000; s = "k" } else { v = n/1000000; s = "M" }
    t = sprintf("%.1f", v); sub(/\.0$/, "", t); printf "%s%s", t, s }'
}
dur() { # segundos -> 3h12m / 2d4h / 45m
  local s=$1
  [ -z "$s" ] && return
  if [ "$s" -ge 86400 ]; then printf '%dd%dh' $((s/86400)) $(((s%86400)/3600))
  elif [ "$s" -ge 3600 ]; then printf '%dh%02dm' $((s/3600)) $(((s%3600)/60))
  else printf '%dm' $(((s+59)/60)); fi
}
if [ -n "${COCKPIT_ASCII:-}" ]; then FULL='#'; EMPTY='.'; else FULL='￭'; EMPTY='･'; fi
bar() { # pct largura
  local p=${1:-0} w=$2 f i out=''
  [ -z "$p" ] && p=0
  [ "$p" -gt 100 ] && p=100; [ "$p" -lt 0 ] && p=0
  f=$(( (p * w + 50) / 100 ))
  for ((i = 0; i < w; i++)); do
    if [ "$i" -lt "$f" ]; then out+=$FULL; else out+=$EMPTY; fi
  done
  printf '%s' "$out"
}
hot() { # cor de alerta acima de 80%
  if [ "${1:-0}" -ge 80 ] 2>/dev/null; then printf '%s' "$WARN"; else printf '%s' "$2"; fi
}

# Largura das barras: cabe em terminal_width (2 barras + textos ~ 46 colunas).
cols=${width:-0}; [ "$cols" -gt 0 ] 2>/dev/null || cols=${COLUMNS:-100}
if [ -n "${COCKPIT_BAR:-}" ]; then W=$COCKPIT_BAR
else W=$(( (cols - 46) / 2 )); [ "$W" -gt 30 ] && W=30; [ "$W" -lt 6 ] && W=6; fi

# ---------- linha 1 ----------
line1="$(c "$PILL") $model $R"
[ -n "$effort" ] && line1+=" $(c "$DIM")|$R $effort"
[ -n "${COCKPIT_STATE:-}" ] && [ -n "$state" ] && [ "$state" != "idle" ] && line1+=" $(c "$DIM")· $state$R"
line1+="  $(c "$DIM;$CTX")tok $R$(c "1;$CTX")$(compact "$used")/$(compact "$total") ($pct%)$R "
if [ "$pct" -ge 80 ] 2>/dev/null; then line1+="$(c "$WARN")$(bar "$pct" "$W")$R"; else line1+="$(bar "$pct" "$W")"; fi
if [ -n "$cost" ]; then
  line1+="  $(LC_ALL=C awk -v v="$cost" 'BEGIN{printf "$%.2f", v}')"
fi

# ---------- linha 2 ----------
quota_seg() { # rótulo pct reset cor
  local label=$1 p=$2 r=$3 col=$4 s
  s="$(c "$DIM;$col")$label $R"
  if [ -z "$p" ]; then
    s+="$(c "$DIM")$(bar 0 "$W")  --$R"
  else
    s+="$(c "$col")$(bar "$p" "$W")$R $(c "1;$(hot "$p" "$col")")$(printf '%3d%%' "$p")$R"
    [ -n "${COCKPIT_RESET:-}" ] && [ -n "$r" ] && s+=" $(c "$DIM")↻$(dur "$r")$R"
  fi
  printf '%s' "$s"
}
line2=" usage  $(quota_seg 5h "$q5" "$r5" "$FIVE")  $(quota_seg 7d "$qw" "$rw" "$WEEK")"

printf '%s\n%s\n' "$line1" "$line2"
