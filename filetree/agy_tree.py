#!/usr/bin/env python3
"""agy-tree: árvore de arquivos estilo IDE que mostra onde o agente do agy está lendo e escrevendo.

Lê o activity.jsonl gravado pelo hook do plugin filetree (agy-turbo) e o git status da pasta.
Visual inspirado no claude-code-filetree (data-goblin, MIT). Roda num painel ao lado do agy (tmux).

Uso: agy-tree [PASTA]
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import shlex
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Input, OptionList, Static, Tree
from textual.widgets.option_list import Option
from textual.widgets.tree import TreeNode

VERSION = "0.2.0"
HIDE = {"node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".DS_Store"}
WALK_SKIP = HIDE | {".git", ".terraform", ".next", "dist", "build", ".cache"}
DATA = os.environ.get("AGY_TURBO_DATA") or os.path.expanduser("~/.gemini/antigravity-cli/plugin_data/agy-turbo")
ACTIVITY_DEFAULT = [
    os.path.join(DATA, "activity.jsonl"),
    os.path.expanduser("~/.gemini/antigravity-cli/plugin_data/filetree/activity.jsonl"),
    os.path.expanduser("~/.gemini/config/plugin_data/filetree/activity.jsonl"),
    os.path.expanduser("~/.local/share/agy-turbo/filetree/activity.jsonl"),
]

# paleta tokyo night (combina com o colorScheme "tokyo night" do agy)
BG = "#1a1b26"
C = {
    "fg": "#c0caf5", "muted": "#565f89", "faint": "#3b4261", "accent": "#7aa2f7", "dir": "#7aa2f7",
    "read": "#bb9af7", "write": "#ff9e64", "git": "#9ece6a",
    "M": "#e0af68", "T": "#e0af68", "A": "#9ece6a", "?": "#9ece6a", "D": "#f7768e", "U": "#f7768e",
    "R": "#7dcfff", "C": "#7dcfff", "add": "#9ece6a", "del": "#f7768e",
    "bar": "#1f2335", "sel": "#283457",
}
SHIMMER = 2.2    # segundos de onda de cor no nome
GLOW = 10.0      # segundos com o nome tingido depois da onda
RANK = {"U": 7, "D": 6, "M": 5, "T": 5, "R": 4, "C": 4, "A": 3, "?": 2}

# ---------- ícones: Nerd Font quando instalada (códigos do claude-code-filetree, MIT), senão Unicode ----------
cp = chr
NERD_NAMES = {"readme.md": 0xf0354, "changelog.md": 0xf0354, "license": 0xe60a, "dockerfile": 0xf0868,
              "makefile": 0xf1064, "package.json": 0xf0626, "package-lock.json": 0xf0626, "tsconfig.json": 0xf0626,
              "requirements.txt": 0xf160e, "pyproject.toml": 0xe6b2, "cargo.toml": 0xe6b2, "go.mod": 0xf0afa,
              ".gitignore": 0xf02a2, ".gitmodules": 0xf0493, ".editorconfig": 0xe652, "yarn.lock": 0xe6a8}
NERD_EXTS = {"py": 0xe606, "js": 0xe60c, "mjs": 0xe60c, "cjs": 0xe60c, "ts": 0xe628, "tsx": 0xe7ba, "jsx": 0xe625,
             "json": 0xe60b, "jsonl": 0xe60b, "yaml": 0xe6a8, "yml": 0xe6a8, "sh": 0xe795, "bash": 0xe795,
             "zsh": 0xe795, "md": 0xf0354, "css": 0xe6b8, "scss": 0xf031c, "html": 0xe736, "go": 0xe627,
             "rs": 0xe68b, "rb": 0xe791, "php": 0xe608, "java": 0xe738, "cs": 0xf031b, "sql": 0xe706,
             "xml": 0xf05c0, "toml": 0xe6b2, "ini": 0xf0bc2, "conf": 0xf0493, "pdf": 0xeaeb, "svg": 0xf0721,
             "png": 0xe60d, "jpg": 0xf0225, "jpeg": 0xf0225, "gz": 0xf05c4, "zip": 0xf05c4, "tar": 0xf05c4,
             "c": 0xe61e, "cpp": 0xe61d, "h": 0xf0af5, "vue": 0xe6a0, "csv": 0xe64a, "txt": 0xf09aa,
             "tf": 0xf1062, "hcl": 0xf1062, "lua": 0xe620}
MEMORY = {"agents.md", "claude.md", "gemini.md", "agents.local.md", "claude.local.md"}
EXT_COLOR = {"py": "#e0af68", "js": "#e0af68", "ts": "#7aa2f7", "tsx": "#7dcfff", "json": "#e0af68",
             "jsonl": "#e0af68", "yaml": "#bb9af7", "yml": "#bb9af7", "toml": "#bb9af7", "sh": "#9ece6a",
             "md": "#7dcfff", "html": "#ff9e64", "css": "#7aa2f7", "go": "#7dcfff", "rs": "#ff9e64",
             "tf": "#bb9af7", "sql": "#e0af68", "txt": "#a9b1d6"}


def has_nerd_font() -> bool:
    mode = os.environ.get("AGY_TREE_GLYPHS", "auto")
    if mode in ("nerd", "plain"):
        return mode == "nerd"
    try:
        out = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, timeout=3).stdout
        return "nerd" in out.lower()
    except (OSError, subprocess.TimeoutExpired):
        return False


NERD = has_nerd_font()
G = {
    "branch": cp(0xe725) if NERD else "⎇", "repo": cp(0xf02a2) if NERD else "◆", "search": cp(0xf002) if NERD else "⌕",
    "up": cp(0xf062) if NERD else "↑", "home": cp(0xf015) if NERD else "⌂", "refresh": cp(0xf021) if NERD else "⟳",
    "eye": cp(0xf06e) if NERD else "◉", "eye_off": cp(0xf070) if NERD else "○", "fold": cp(0xf0d6c) if NERD else "⊟",
    "split": cp(0xf0db) if NERD else "◫", "follow": cp(0xf05b7) if NERD else "◎", "brain": cp(0xf09d1) if NERD else "§",
    "link": cp(0xf481) if NERD else "→", "ignored": cp(0xf05e) if NERD else "⊘",
}


def file_icon(path: Path, is_dir: bool, open_: bool) -> tuple[str, str]:
    name = path.name.lower()
    if is_dir:
        return (cp(0xe5fe if open_ else 0xe5ff) if NERD else "▪"), C["dir"]
    if name in MEMORY:
        return G["brain"], C["read"]
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    color = EXT_COLOR.get(ext, "#7f86a8")
    if NERD:
        return cp(NERD_NAMES.get(name) or NERD_EXTS.get(ext) or 0xf0214), color
    return "•", color


def blend(a: str, b: str, t: float) -> str:
    a_, b_ = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a_, b_))


# ---------- dados ----------
@dataclass
class Entry:
    path: Path
    is_dir: bool
    loaded: bool = False


@dataclass
class GitState:
    repo: str = ""
    branch: str = ""
    upstream: str = ""
    ahead: int = 0
    behind: int = 0
    files: dict[str, str] = field(default_factory=dict)
    dirs: dict[str, str] = field(default_factory=dict)
    dir_counts: dict[str, Counter] = field(default_factory=dict)
    numstat: dict[str, tuple[int, int]] = field(default_factory=dict)
    dir_numstat: dict[str, tuple[int, int]] = field(default_factory=dict)
    ignored: set[str] = field(default_factory=set)


_IGNORED: dict[str, tuple[float, set]] = {}


def _ancestors(path: str, repo: str):
    d = os.path.dirname(path)
    while len(d) >= len(repo):
        yield d
        if d == repo:
            break
        d = os.path.dirname(d)


def git_state(root: Path) -> GitState:
    st = GitState()

    def run(*args, timeout=5):
        return subprocess.run(["git", "-C", st.repo or str(root), *args], capture_output=True, text=True,
                              timeout=timeout)
    try:
        top = run("rev-parse", "--show-toplevel", timeout=3)
        if top.returncode != 0:
            return st
        st.repo = top.stdout.strip()
        out = run("status", "--porcelain=v1", "-b", "-z", "--untracked-files=all").stdout
    except (OSError, subprocess.TimeoutExpired):
        return st
    parts = out.split("\0")
    i = 0
    while i < len(parts):
        rec = parts[i]
        i += 1
        if not rec:
            continue
        if rec.startswith("## "):
            br, _, rest = rec[3:].partition("...")
            st.branch = br.replace("No commits yet on ", "").replace("HEAD (no branch)", "HEAD")
            up, _, ab = rest.partition(" ")
            st.upstream = up
            for tok in ab.strip("[]").split(", "):
                if tok.startswith("ahead "):
                    st.ahead = int(tok[6:])
                elif tok.startswith("behind "):
                    st.behind = int(tok[7:])
            continue
        xy, rel = rec[:2], rec[3:]
        if xy[0] in "RC":
            i += 1
        letter = "?" if xy == "??" else next((c for c in xy if c != " "), "M")
        ab = os.path.join(st.repo, rel)
        st.files[ab] = letter
        for d in _ancestors(ab, st.repo):
            st.dir_counts.setdefault(d, Counter())[letter] += 1
            if RANK.get(letter, 0) > RANK.get(st.dirs.get(d, ""), 0):
                st.dirs[d] = letter
    try:
        for line in run("diff", "--numstat", "HEAD").stdout.splitlines():
            a, d_, rel = (line.split("\t") + ["", "", ""])[:3]
            if a.isdigit() and d_.isdigit():
                ab = os.path.join(st.repo, rel)
                st.numstat[ab] = (int(a), int(d_))
                for d in _ancestors(ab, st.repo):
                    x, y = st.dir_numstat.get(d, (0, 0))
                    st.dir_numstat[d] = (x + int(a), y + int(d_))
        cached = _IGNORED.get(st.repo)
        if cached and time.time() - cached[0] < 30:      # lista de ignorados: cara em repo grande, cache de 30 s
            st.ignored = cached[1]
        else:
            for rel in run("ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z",
                           timeout=3).stdout.split("\0"):
                if rel:
                    st.ignored.add(os.path.join(st.repo, rel.rstrip("/")))
            _IGNORED[st.repo] = (time.time(), st.ignored)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return st


def human_size(n: float) -> str:
    for unit in ("B", "K", "M", "G"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}T"


def age(ts: float) -> str:
    d = max(0, time.time() - ts)
    if d < 60:
        return "now"
    if d < 3600:
        return f"{int(d // 60)}m"
    if d < 86400:
        return f"{int(d // 3600)}h"
    if d < 86400 * 7:
        return f"{int(d // 86400)}d"
    return time.strftime("%b %d", time.localtime(ts))


# ---------- árvore ----------
class FileTree(Tree[Entry]):
    COLUMNS = ("date", "age", "size", "none")

    def __init__(self, root: Path, app_state: "AgyTree") -> None:
        super().__init__(root.name or str(root), data=Entry(root, True))
        self.state = app_state
        self.show_root = False
        self.guide_depth = 2
        self.auto_expand = False

    def load(self, node: TreeNode[Entry]) -> None:
        e = node.data
        if e is None or not e.is_dir or e.loaded:
            return
        e.loaded = True
        node.remove_children()
        try:
            items = list(os.scandir(e.path))
        except OSError:
            return
        items = [i for i in items if i.name not in HIDE and (self.state.show_hidden or not i.name.startswith("."))]
        items.sort(key=lambda i: (not i.is_dir(), i.name.lower()))
        for i in items:
            ent = Entry(Path(i.path), i.is_dir())
            if ent.is_dir:
                node.add(i.name, data=ent, allow_expand=True)
            else:
                node.add_leaf(i.name, data=ent)

    def walk(self, node: TreeNode[Entry]):
        stack = [node]
        while stack:
            n = stack.pop()
            yield n
            stack.extend(n.children)

    def reload(self, node: TreeNode[Entry]) -> None:
        if node.data is None or not node.data.is_dir:
            return
        opened = {str(n.data.path) for n in self.walk(node) if n.data and n.is_expanded and n is not node}
        node.data.loaded = False
        self.load(node)
        for n in list(self.walk(node)):
            if n is not node and n.data and str(n.data.path) in opened:
                self.load(n)
                n.expand()

    def find(self, path: Path, create: bool = True) -> TreeNode[Entry] | None:
        root = self.root.data.path
        try:
            rel = path.resolve().relative_to(root.resolve())
        except (ValueError, OSError):
            return None
        node = self.root
        for part in rel.parts:
            if not create and not (node.data and node.data.loaded):
                return None
            self.load(node)
            nxt = next((c for c in node.children if c.data and c.data.path.name == part), None)
            if nxt is None and create and node.data:
                node.data.loaded = False
                self.load(node)
                nxt = next((c for c in node.children if c.data and c.data.path.name == part), None)
            if nxt is None:
                return None
            node = nxt
        return node

    def depth(self, node: TreeNode[Entry]) -> int:
        d, n = 0, node.parent
        while n is not None and n is not self.root:
            d += 1
            n = n.parent
        return d

    def value(self, e: Entry) -> str:
        col = self.state.column
        if col == "none" or e.is_dir:
            return ""
        try:
            st = e.path.lstat()
        except OSError:
            return ""
        if col == "date":
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
        if col == "age":
            return age(st.st_mtime)
        return human_size(st.st_size)

    def git_text(self, e: Entry) -> Text:
        g = self.state.git
        p = str(e.path)
        t = Text()
        ns = g.dir_numstat.get(p) if e.is_dir else g.numstat.get(p)
        if ns:
            t.append(f"+{ns[0]} ", style=C["add"])
            t.append(f"-{ns[1]} ", style=C["del"])
        if e.is_dir:
            counts = g.dir_counts.get(p) or {}
            for letter in sorted(counts, key=lambda k: -RANK.get(k, 0)):
                t.append(f"{letter}:{counts[letter]} ", style=C.get(letter, C["M"]))
        else:
            letter = g.files.get(p)
            if letter:
                t.append(f"{letter} ", style=Style(color=C.get(letter, C["M"]), bold=True))
        t.rstrip()
        return t

    def render_label(self, node: TreeNode[Entry], base_style: Style, style: Style) -> Text:
        e = node.data
        if e is None:
            return Text(str(node.label))
        s = self.state
        p = str(e.path)
        letter = s.git.dirs.get(p) if e.is_dir else s.git.files.get(p)
        dim = e.path.name.startswith(".") or p in s.git.ignored

        label = Text()
        label.append(("▾ " if node.is_expanded else "▸ ") if e.is_dir else "  ", style=C["muted"])
        glyph, gcolor = file_icon(e.path, e.is_dir, node.is_expanded)
        name_color = C.get(letter, C["M"]) if letter else (C["dir"] if e.is_dir else C["fg"])
        if dim:
            name_color, gcolor = blend(name_color, BG, 0.55), blend(gcolor, BG, 0.55)
        label.append(glyph + " ", style=gcolor)
        name = e.path.name
        start = label.cell_len
        label.append(name, style=Style(color=name_color, bold=e.is_dir and not dim))
        if e.path.is_symlink():
            label.append(" " + G["link"], style=C["muted"])

        act = s.activity.get(p)
        if act:
            kind, ts = act
            a = time.time() - ts
            col = C[kind]
            if a < SHIMMER:
                # onda de cor andando pelo nome, como o shimmer do original
                pos = a / SHIMMER * (len(name) + 8) - 4
                for i in range(len(name)):
                    k = max(0.0, 1 - abs(i - pos) / 3.5)
                    label.stylize(Style(color=blend(col, "#ffffff", 0.6 * k), bold=True), start + i, start + i + 1)
            elif a < GLOW:
                fade = 0.85 - 0.6 * (a - SHIMMER) / (GLOW - SHIMMER)
                label.stylize(Style(color=blend(name_color, col, fade)), start, start + len(name))

        right = self.git_text(e)
        if p in s.git.ignored and not e.is_dir:
            right.append((" " if right else "") + G["ignored"], style=C["muted"])
        val = self.value(e)
        if val:
            right.append(("  " if right else "") + val, style=blend(C["muted"], BG, 0.45 if dim else 0.1))
        avail = self.size.width - 2 - self.depth(node) * self.guide_depth
        pad = avail - label.cell_len - right.cell_len
        if pad < 1:
            label.truncate(max(8, avail - right.cell_len - 1), overflow="ellipsis")
            pad = max(1, avail - label.cell_len - right.cell_len)
        label.append(" " * pad)
        label.append_text(right)
        return label

    def on_resize(self) -> None:
        self._invalidate()


class Preview(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Static(id="preview-body")

    def show(self, path: Path | None) -> None:
        body = self.query_one("#preview-body", Static)
        if path is None:
            body.update("")
            return
        if path.is_dir():
            try:
                kids = list(os.scandir(path))
                n_dir = sum(1 for k in kids if k.is_dir())
                body.update(Text(f"{path.name}/  ·  {n_dir} pastas, {len(kids) - n_dir} arquivos", style=C["muted"]))
            except OSError as exc:
                body.update(str(exc))
            return
        try:
            size = path.stat().st_size
            if size > 512 * 1024:
                body.update(Text(f"{path.name}: {human_size(size)}, grande demais para preview", style=C["muted"]))
                return
            raw = path.read_bytes()
            if b"\0" in raw[:4096]:
                body.update(Text(f"{path.name}: arquivo binário ({human_size(size)})", style=C["muted"]))
                return
            code = raw.decode("utf-8", errors="replace")
            body.update(Syntax(code, Syntax.guess_lexer(str(path), code), theme="monokai", line_numbers=True,
                               background_color="#16161e"))
        except OSError as exc:
            body.update(str(exc))
        self.scroll_home(animate=False)


HELP = f"""[b {C['accent']}]Atalhos[/]

  [b]j k[/]  ↓ ↑      mover
  [b]l[/]  → enter    abrir pasta · preview do arquivo
  [b]h[/]  ←          fechar pasta · subir
  [b]p[/]             mostrar/ocultar preview
  [b]o[/]             abrir no editor
  [b]s[/]  /          buscar pelo nome
  [b]f[/]             seguir o agente
  [b].[/]             mostrar/ocultar ocultos
  [b]c[/]             coluna: data · idade · tamanho · nada
  [b]z[/]             recolher tudo
  [b]g G[/]           topo · fim
  [b]r[/]             recarregar
  [b]y[/]             copiar caminho
  [b]u[/]             subir a raiz (⌂ volta)
  [b]?[/]             esta ajuda   ·   [b]q[/] sair

  [{C['read']}]lendo[/]  [{C['write']}]escrevendo[/]  [{C['git']}]git[/]   o nome brilha quando o agente mexe
  [{C['M']}]M[/] alterado  [{C['A']}]?[/] novo  [{C['D']}]D[/] apagado   [{C['add']}]+N[/] [{C['del']}]-N[/] linhas
"""


class AgyTree(App):
    CSS = f"""
    Screen {{ background: {BG}; color: {C['fg']}; }}
    #top, #gitrow, #cols {{ height: 1; padding: 0 1; }}
    #title, #gitleft {{ width: 1fr; }}
    #toolbar, #gitright, #colright {{ width: auto; }}
    #search {{ height: 1; border: none; padding: 0 1; margin: 1 0 0 0; background: {C['bar']}; color: {C['fg']}; }}
    #search:focus {{ background: #24283b; border: none; }}
    #search > .input--placeholder {{ color: {C['muted']}; }}
    #cols {{ color: {C['muted']}; }}
    #colname {{ width: 1fr; padding: 0 0 0 5; color: {C['muted']}; }}
    #results {{ display: none; height: auto; max-height: 50%; background: {C['bar']}; border: none; padding: 0 1; }}
    #results.on {{ display: block; }}
    #body {{ height: 1fr; }}
    FileTree {{ background: {BG}; padding: 0 0 0 1; scrollbar-size-vertical: 1;
               scrollbar-color: {C['faint']}; scrollbar-background: {BG}; }}
    FileTree > .tree--cursor {{ background: {C['sel']}; text-style: none; }}
    FileTree:focus > .tree--cursor {{ background: {C['sel']}; text-style: none; }}
    FileTree > .tree--guides {{ color: {BG}; }}
    FileTree > .tree--guides-hover {{ color: {BG}; }}
    FileTree > .tree--guides-selected {{ color: {BG}; }}
    FileTree > .tree--highlight-line {{ background: #1f2335; }}
    Preview {{ height: 45%; display: none; background: #16161e; border-top: solid {C['faint']}; }}
    Preview.on {{ display: block; }}
    #help {{ display: none; padding: 1 2; height: 1fr; }}
    #help.on {{ display: block; }}
    #footer {{ height: 1; padding: 0 1; color: {C['muted']}; }}
    #effbar {{ height: auto; max-height: 2; padding: 0 1; background: {C['bar']}; }}
    """
    BINDINGS = [
        Binding("q", "quit", "sair"),
        Binding("j", "down", show=False), Binding("k", "up", show=False),
        Binding("h", "collapse", show=False), Binding("left", "collapse", show=False),
        Binding("l", "expand", show=False), Binding("right", "expand", show=False),
        Binding("g", "top", show=False), Binding("G", "bottom", show=False),
        Binding("p", "preview", show=False), Binding("f", "follow", show=False),
        Binding("s", "search", show=False), Binding("slash", "search", show=False),
        Binding("full_stop", "hidden", show=False), Binding("c", "column", show=False),
        Binding("z", "collapse_all", show=False), Binding("r", "refresh", show=False),
        Binding("o", "open", show=False), Binding("y", "copy", show=False),
        Binding("u", "up_root", show=False), Binding("question_mark", "help", show=False),
        Binding("escape", "escape", show=False),
    ]

    def __init__(self, root: Path, activity_file: str | None) -> None:
        super().__init__()
        self.start_root = root.resolve()
        self.root_path = self.start_root
        self.git = GitState()
        self.activity: dict[str, tuple[str, float]] = {}
        self.activity_files = [activity_file] if activity_file else ACTIVITY_DEFAULT
        self.offsets: dict[str, int] = {}
        self.follow = True
        self.show_hidden = True
        self.column = "date"
        self.last_cmd = ""
        self.last_touch: tuple[str, str] | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="top"):
            yield Static(id="title")
            yield Static(id="toolbar")
        with Horizontal(id="gitrow"):
            yield Static(id="gitleft")
            yield Static(id="gitright")
        yield Input(placeholder=f"{G['search']} search", id="search")
        yield OptionList(id="results")
        with Horizontal(id="cols"):
            yield Static("Name", id="colname")
            yield Static(id="colright")
        with Vertical(id="body"):
            yield FileTree(self.root_path, self)
            yield Static(HELP, id="help")
            yield Preview()
        yield Static(id="effbar")
        yield Static(id="footer")

    @property
    def tree(self) -> FileTree:
        return self.query_one(FileTree)

    def on_mount(self) -> None:
        self._mount_root()
        for f in self.activity_files:
            try:
                self.offsets[f] = os.path.getsize(f)
            except OSError:
                self.offsets[f] = 0
        self.set_interval(0.1, self.tick)       # barato quando nada mudou; redesenha só com brilho ativo
        self.set_interval(3.0, self.refresh_git)
        self.set_interval(1.0, self.update_effbar)
        self.update_effbar()

    # ---------- barra do effortless (ao vivo: a statusline do agy não atualiza parada) ----------
    def _json(self, name: str) -> dict:
        try:
            with open(os.path.join(DATA, name), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def update_effbar(self) -> None:
        sl, st, cf = self._json("statusline.json"), self._json("effortless.json"), self._json("config.json")
        bar = self.query_one("#effbar", Static)
        if not sl and not st:
            bar.display = False
            return
        bar.display = True
        model = sl.get("model") or {}
        cur = model.get("effort") or st.get("current") or "?"
        pct = float((sl.get("context_window") or {}).get("used_percentage") or 0)
        t = Text()
        t.append("✦ ", style=C["read"])
        t.append(cur, style=f"bold {C['fg']}")
        # cache: tempo desde a última chamada ao modelo contra um TTL estimado
        last = None
        tp = sl.get("transcript_path")
        if tp:
            try:
                with open(tp, "rb") as f:
                    f.seek(0, 2)
                    f.seek(max(0, f.tell() - 60_000))
                    for line in reversed(f.read().decode("utf-8", errors="replace").splitlines()):
                        try:
                            d = json.loads(line)
                        except ValueError:
                            continue
                        if d.get("type") == "PLANNER_RESPONSE" and d.get("created_at"):
                            last = (calendar.timegm(time.strptime(d["created_at"][:19], "%Y-%m-%dT%H:%M:%S")),
                                    int(d.get("cache_read_tokens") or 0))
                            break
            except OSError:
                pass
        if last:
            name = (model.get("display_name") or "").lower()
            ttl = float(os.environ.get("AGY_CACHE_TTL_MIN") or (60 if "claude" in name else 5)) * 60
            left = ttl - (time.time() - last[0])
            if left > 0:
                m, sec = divmod(int(left), 60)
                t.append(f" · cache {m}:{sec:02d}", style=C["git"] if left > 60 else C["M"])
                if last[1]:
                    t.append(f" ({last[1] // 1000}k)", style=C["muted"])
            else:
                t.append(" · cache frio", style=C["muted"])
        t.append(f" · {pct:.0f}% context", style=C["del"] if pct >= 80 else C["M"] if pct >= 70 else C["fg"])
        auto = cf.get("auto", True)
        t.append("   ")
        t.append("auto" if auto else "manual", style=f"bold {C['read']}" if auto else C["muted"])
        hint = {"compacting": "compactando…", "compact": "contexto cheio: /compact",
                "handoff": "assunto novo: /handoff"}.get(st.get("hint") or "")
        if hint:
            t.append("  " + hint, style=C["M"])
        gauge = Text()
        for lvl in st.get("levels") or ["low", "medium", "high"]:
            gauge.append(f"[{lvl}] " if lvl == cur else f"{lvl} ", style=f"bold {C['read']}" if lvl == cur else C["muted"])
        if st.get("pending"):
            gauge.append(f"→ {st['pending']} depois desta resposta  ", style=C["muted"])
        if st.get("reason") and auto:
            gauge.append(str(st["reason"])[:60], style=C["muted"])
        t.append("\n")
        t.append_text(gauge)
        bar.update(t)

    def _mount_root(self) -> None:
        t = self.tree
        t.root.data = Entry(self.root_path, True)
        t.load(t.root)
        t.root.expand()
        t.focus()
        t.cursor_line = 0
        self.refresh_git()
        self.update_chrome()

    # ---------- dados ----------
    @work(thread=True, exclusive=True, group="git")
    def refresh_git(self) -> None:
        st = git_state(self.root_path)
        self.call_from_thread(self._set_git, st)

    def _set_git(self, st: GitState) -> None:
        self.git = st
        self.redraw()

    def redraw(self) -> None:
        self.tree._invalidate()
        self.tree.refresh()
        self.update_chrome()

    def read_activity(self) -> list[dict]:
        events = []
        for f in self.activity_files:
            try:
                size = os.path.getsize(f)
            except OSError:
                continue
            off = self.offsets.get(f, 0)
            if size < off:
                off = 0
            if size == off:
                continue
            with open(f, "rb") as fh:
                fh.seek(off)
                chunk = fh.read()
            self.offsets[f] = off + len(chunk)
            for line in chunk.decode("utf-8", errors="replace").splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    pass
        return events

    def tick(self) -> None:
        root = str(self.root_path)
        changed = git_dirty = False
        target = None
        for ev in self.read_activity():
            kind = ev.get("kind")
            if kind == "cmd":
                cwd = ev.get("cwd", "")
                if cwd.startswith(root) or root.startswith(cwd):
                    self.last_cmd = ev.get("cmd", "")
                    changed = True
                continue
            if kind == "git":
                git_dirty = True
            for p in ev.get("paths") or []:
                p = os.path.normpath(p)
                if not (p == root or p.startswith(root + os.sep)):
                    continue
                k = kind if kind in ("read", "write", "git") else "read"
                self.activity[p] = (k, ev.get("t", time.time()))
                self.last_touch = (k, os.path.relpath(p, root))
                if k in ("write", "git"):
                    git_dirty = True
                    parent = self.tree.find(Path(p).parent, create=self.follow)
                    if parent is not None and parent.data and parent.data.loaded:
                        self.tree.reload(parent)
                target = p
                changed = True
        if git_dirty:
            self.refresh_git()
        if target and self.follow:
            node = self.tree.find(Path(target))
            if node is not None:
                n = node.parent
                while n is not None:
                    n.expand()
                    n = n.parent
                self.call_after_refresh(self.tree.scroll_to_node, node, animate=False)
        now = time.time()
        old = [k for k, (_, ts) in self.activity.items() if now - ts > GLOW]
        for k in old:
            del self.activity[k]
        shimmering = any(now - ts < SHIMMER for _, ts in self.activity.values())
        self._ticks = getattr(self, "_ticks", 0) + 1
        # 10 quadros/s só durante a onda de cor; com marcas paradas, 1 quadro/s
        if changed or old or shimmering or (self.activity and self._ticks % 10 == 0):
            self.redraw()

    # ---------- cabeçalho e rodapé ----------
    def update_chrome(self) -> None:
        g = self.git
        name = self.root_path.name or str(self.root_path)
        title = Text.assemble((G["repo"] + " ", C["accent"]), (name, f"bold {C['accent']}"))
        if self.root_path != self.start_root:
            title.append("  (⌂ volta)", style=C["muted"])
        self.query_one("#title", Static).update(title)
        eye = G["eye"] if self.show_hidden else G["eye_off"]
        fcol = C["accent"] if self.follow else C["muted"]
        m = C["muted"]
        tb = (f"[{m}][@click=app.up_root]{G['up']}[/] [@click=app.home_root]{G['home']}[/] "
              f"[@click=app.refresh]{G['refresh']}[/] [@click=app.hidden]{eye}[/] "
              f"[@click=app.collapse_all]{G['fold']}[/] [@click=app.preview]{G['split']}[/] "
              f"[/][{fcol}][@click=app.follow]{G['follow']}[/][/] [{m}][@click=app.help]?[/][/]")
        self.query_one("#toolbar", Static).update(tb)

        if g.branch:
            left = Text.assemble((G["branch"] + " ", C["git"]), (g.branch, f"bold {C['fg']}"))
            if g.ahead:
                left.append(f" ↑{g.ahead}", style=C["git"])
            if g.behind:
                left.append(f" ↓{g.behind}", style=C["del"])
            if g.upstream:
                left.append(f" {g.upstream}", style=C["faint"])
            right = Text()
            total = Counter(g.files.values())
            if total:
                a = sum(x for x, _ in g.numstat.values())
                d = sum(y for _, y in g.numstat.values())
                if a or d:
                    right.append(f"+{a} ", style=C["add"])
                    right.append(f"-{d} ", style=C["del"])
                for letter in sorted(total, key=lambda k: -RANK.get(k, 0)):
                    right.append(f"{letter}:{total[letter]} ", style=C.get(letter, C["M"]))
                right.rstrip()
            else:
                right.append("clean", style=C["muted"])
        else:
            left, right = Text("sem repositório git", style=C["muted"]), Text()
        self.query_one("#gitleft", Static).update(left)
        self.query_one("#gitright", Static).update(right)
        col = {"date": "Modified", "age": "Age", "size": "Size", "none": ""}[self.column]
        self.query_one("#colright", Static).update(Text(f"Git   {col}".rstrip(), style=C["muted"]))

        foot = Text()
        if self.last_touch:
            k, rel = self.last_touch
            foot.append({"read": "lendo ", "write": "escrevendo ", "git": "git "}[k], style=C[k])
            foot.append(rel, style=C["fg"])
        if self.last_cmd:
            foot.append(("   " if foot else "") + "$ " + self.last_cmd.splitlines()[0][:150], style=C["muted"])
        if not foot:
            foot = Text("aguardando o agente…   ? atalhos", style=C["muted"])
        self.query_one("#footer", Static).update(foot)

    # ---------- eventos da árvore ----------
    def current(self) -> Entry | None:
        node = self.tree.cursor_node
        return node.data if node else None

    @on(Tree.NodeExpanded)
    def _expanded(self, event: Tree.NodeExpanded) -> None:
        self.tree.load(event.node)

    @on(Tree.NodeHighlighted)
    def _highlighted(self, event: Tree.NodeHighlighted) -> None:
        pv = self.query_one(Preview)
        if pv.has_class("on") and event.node.data:
            pv.show(event.node.data.path)

    @on(Tree.NodeSelected)
    def _selected(self, event: Tree.NodeSelected) -> None:
        e = event.node.data
        if e is None:
            return
        if e.is_dir:
            self.tree.load(event.node)
            event.node.toggle()
        else:
            pv = self.query_one(Preview)
            pv.add_class("on")
            pv.show(e.path)

    # ---------- ações ----------
    def action_down(self) -> None:
        self.tree.action_cursor_down()

    def action_up(self) -> None:
        self.tree.action_cursor_up()

    def action_expand(self) -> None:
        node = self.tree.cursor_node
        if node and node.data and node.data.is_dir:
            self.tree.load(node)
            if node.is_expanded and node.children:
                self.tree.move_cursor(node.children[0])
            node.expand()
        elif node and node.data:
            pv = self.query_one(Preview)
            pv.add_class("on")
            pv.show(node.data.path)

    def action_collapse(self) -> None:
        node = self.tree.cursor_node
        if node is None:
            return
        if node.is_expanded and node.data and node.data.is_dir:
            node.collapse()
        elif node.parent is not None and node.parent is not self.tree.root:
            self.tree.move_cursor(node.parent)
            node.parent.collapse()

    def action_collapse_all(self) -> None:
        for n in self.tree.root.children:
            n.collapse_all()
        self.tree.cursor_line = 0

    def action_top(self) -> None:
        self.tree.cursor_line = 0
        self.tree.scroll_home(animate=False)

    def action_bottom(self) -> None:
        self.tree.cursor_line = self.tree.last_line
        self.tree.scroll_end(animate=False)

    def action_preview(self) -> None:
        pv = self.query_one(Preview)
        pv.toggle_class("on")
        if pv.has_class("on"):
            e = self.current()
            pv.show(e.path if e else None)

    def action_follow(self) -> None:
        self.follow = not self.follow
        self.notify("seguindo o agente" if self.follow else "parou de seguir o agente", timeout=2)
        self.update_chrome()

    def action_hidden(self) -> None:
        self.show_hidden = not self.show_hidden
        self.tree.reload(self.tree.root)
        self.update_chrome()

    def action_column(self) -> None:
        cols = FileTree.COLUMNS
        self.column = cols[(cols.index(self.column) + 1) % len(cols)]
        self.redraw()

    def action_refresh(self) -> None:
        self.tree.reload(self.tree.root)
        self.refresh_git()

    def action_up_root(self) -> None:
        if self.root_path.parent != self.root_path:
            self.root_path = self.root_path.parent
            self._mount_root()

    def action_home_root(self) -> None:
        if self.root_path != self.start_root:
            self.root_path = self.start_root
            self._mount_root()

    def action_help(self) -> None:
        h = self.query_one("#help")
        h.toggle_class("on")
        self.tree.display = not h.has_class("on")

    def action_copy(self) -> None:
        e = self.current()
        if e:
            self.copy_to_clipboard(str(e.path))
            self.notify(f"copiado: {e.path}", timeout=2)

    def action_open(self) -> None:
        e = self.current()
        if not e or e.is_dir:
            return
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        if editor:
            with self.suspend():
                subprocess.run(shlex.split(editor) + [str(e.path)])
        else:
            subprocess.Popen(["xdg-open", str(e.path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)

    def action_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_escape(self) -> None:
        self.query_one("#search", Input).value = ""
        for w in ("#results", "#help", "Preview"):
            self.query_one(w).remove_class("on")
        self.tree.display = True
        self.tree.focus()

    # ---------- busca ----------
    @on(Input.Changed, "#search")
    def _search(self, event: Input.Changed) -> None:
        q = event.value.strip().lower()
        res = self.query_one("#results", OptionList)
        res.clear_options()
        if len(q) < 2:
            res.remove_class("on")
            return
        hits = []
        for dirpath, dirnames, filenames in os.walk(self.root_path):
            dirnames[:] = [d for d in dirnames if d not in WALK_SKIP]
            for name in dirnames + filenames:
                if q in name.lower():
                    hits.append(os.path.relpath(os.path.join(dirpath, name), self.root_path))
            if len(hits) >= 300:
                break
        hits.sort(key=lambda h: (not os.path.basename(h).lower().startswith(q), len(h)))
        opts = []
        for h in hits[:60]:
            base, parent = os.path.basename(h), os.path.dirname(h)
            t = Text(parent + "/" if parent else "", style=C["muted"])
            i = base.lower().find(q)
            t.append(base[:i], style=C["fg"])
            t.append(base[i:i + len(q)], style=f"bold {C['write']}")
            t.append(base[i + len(q):], style=C["fg"])
            opts.append(Option(t, id=h))
        res.add_options(opts)
        res.set_class(bool(opts), "on")

    @on(Input.Submitted, "#search")
    def _search_go(self, event: Input.Submitted) -> None:
        res = self.query_one("#results", OptionList)
        if res.option_count:
            self._jump(res.get_option_at_index(res.highlighted or 0).id)

    @on(OptionList.OptionSelected, "#results")
    def _result(self, event: OptionList.OptionSelected) -> None:
        self._jump(event.option.id)

    def _jump(self, rel: str | None) -> None:
        if not rel:
            return
        node = self.tree.find(self.root_path / rel)
        self.action_escape()
        if node is not None:
            n = node.parent
            while n is not None:
                n.expand()
                n = n.parent
            self.call_after_refresh(self.tree.move_cursor, node)

    def on_key(self, event) -> None:
        if self.query_one("#search", Input).has_focus and event.key in ("down", "up"):
            res = self.query_one("#results", OptionList)
            if res.option_count:
                res.action_cursor_down() if event.key == "down" else res.action_cursor_up()
                event.stop()


def main() -> None:
    ap = argparse.ArgumentParser(prog="agy-tree", description=__doc__.split("\n\n")[0])
    ap.add_argument("path", nargs="?", default=os.getcwd())
    ap.add_argument("--activity", help="arquivo activity.jsonl (padrão: o do plugin filetree)")
    ap.add_argument("--version", action="version", version=VERSION)
    a = ap.parse_args()
    root = Path(a.path).expanduser()
    if not root.is_dir():
        sys.exit(f"agy-tree: pasta não encontrada: {root}")
    AgyTree(root, a.activity).run()


if __name__ == "__main__":
    main()
