#!/usr/bin/env bash
set -uo pipefail
rm -f "$HOME/.local/bin/agy-tree" "$HOME/.local/bin/agy-turbo"
agy plugin uninstall filetree
[ -f "$HOME/.bashrc" ] && sed -i '/# >>> agy-turbo >>>/,/# <<< agy-turbo <<</d' "$HOME/.bashrc"
echo "filetree removido (o venv em ~/.local/share/agy-turbo/venv fica; apague à mão se quiser)."
