"""Hook SessionStart: se o agy roda dentro do tmux, abre o agy-tree num painel à direita (uma vez por janela).

Desligar: AGY_TREE=0.  Largura: AGY_TREE_WIDTH (padrão 34%).  Sempre responde "{}".
"""
import json
import os
import shutil
import subprocess
import sys


def open_tree(ev):
    pane = os.environ.get("TMUX_PANE")
    if not os.environ.get("TMUX") or not pane or os.environ.get("AGY_TREE", "1") == "0":
        return
    tree = shutil.which("agy-tree") or os.path.expanduser("~/.local/bin/agy-tree")
    if not os.path.exists(tree):
        tree = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "agy-tree")
    if not os.path.exists(tree):
        return
    titles = subprocess.run(["tmux", "list-panes", "-t", pane, "-F", "#{pane_title}"],
                            capture_output=True, text=True, timeout=3).stdout.split("\n")
    if "agy-tree" in titles:
        return
    cwd = ev.get("cwd") or (ev.get("workspacePaths") or [os.getcwd()])[0]
    subprocess.run(["tmux", "split-window", "-h", "-d", "-l", os.environ.get("AGY_TREE_WIDTH", "34%"),
                    "-t", pane, "-c", cwd, tree, cwd], timeout=3)


if __name__ == "__main__":
    try:
        open_tree(json.loads(sys.stdin.read() or "{}"))
    except Exception:
        pass
    print("{}")
