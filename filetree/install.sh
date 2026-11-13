#!/usr/bin/env bash
# Instala o filetree do agy-turbo: venv com Textual, comandos agy-tree/agy-turbo em ~/.local/bin e o plugin de hooks.
set -euo pipefail
DIR=$(cd "$(dirname "$0")/.." && pwd)
VENV=${AGY_TURBO_VENV:-$HOME/.local/share/agy-turbo/venv}
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade "textual==8.2.8"
mkdir -p "$HOME/.local/bin"
ln -sf "$DIR/bin/agy-tree" "$HOME/.local/bin/agy-tree"
ln -sf "$DIR/bin/agy-turbo" "$HOME/.local/bin/agy-turbo"
chmod +x "$DIR/bin/agy-tree" "$DIR/bin/agy-turbo"
agy plugin install "$DIR/plugins/filetree"
echo "filetree instalado: rode 'agy-turbo' (agy + árvore) ou 'agy-tree' num terminal ao lado."
command -v tmux >/dev/null || echo "Dica: com tmux (sudo apt install tmux) a árvore abre ao lado do agy na mesma janela."
