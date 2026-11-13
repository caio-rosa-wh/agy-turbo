# agy-turbo: faz o comando "agy" interativo abrir com a árvore de arquivos ao lado (tmux por baixo).
# Carregado pelo ~/.bashrc (filetree/install.sh). AGY_TREE=0 agy abre o agy puro.
agy() {
  local a
  if [ "${AGY_TREE:-1}" = "0" ] || [ ! -t 0 ] || [ ! -t 1 ] || ! command -v tmux >/dev/null 2>&1 \
     || ! command -v agy-turbo >/dev/null 2>&1; then
    command agy "$@"; return
  fi
  case "${1:-}" in
    acp|agent|agents|changelog|help|install|mcp|mic-serve|models|plugin|plugins|remote-control|update)
      command agy "$@"; return ;;
  esac
  for a in "$@"; do
    case "$a" in
      -p|--print|--prompt|--prompt=*|--print=*|-h|--help|--version|--output-format|--output-format=*)
        command agy "$@"; return ;;
    esac
  done
  agy-turbo "$@"
}
