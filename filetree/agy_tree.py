#!/usr/bin/env python3
"""agy-tree: árvore de arquivos estilo IDE que mostra onde o agente do agy está lendo e escrevendo.

Lê o activity.jsonl gravado pelo hook do plugin filetree (agy-turbo) e o git status da pasta.
Roda num pane ao lado do agy (tmux) ou numa janela própria.

Uso: agy-tree [PASTA]
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
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

VERSION = "0.1.0"
IGNORE = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache", ".ruff_cache",
          ".terraform", ".next", "dist", "build", ".cache", ".idea", ".DS_Store"}
ACTIVITY_DEFAULT = [
    os.path.expanduser("~/.gemini/antigravity-cli/plugin_data/filetree/activity.jsonl"),
    os.path.expanduser("~/.gemini/config/plugin_data/filetree/activity.jsonl"),
    os.path.expanduser("~/.local/share/agy-turbo/filetree/activity.jsonl"),
]

# paleta (tokyo night)
C = {
    "fg": "#c0caf5", "muted": "#565f89", "dir": "#7aa2f7", "accent": "#7dcfff",
    "read": "#bb9af7", "write": "#ff9e64", "git": "#9ece6a",
    "M": "#e0af68", "A": "#9ece6a", "?": "#9ece6a", "D": "#f7768e", "R": "#7dcfff", "U": "#f7768e",
    "add": "#9ece6a", "del": "#f7768e", "sel": "#283457",
}
FLASH = 1.6      # segundos de brilho forte
GLOW = 10.0      # segundos até apagar a marca de atividade


@dataclass
class Entry:
    path: Path
    is_dir: bool
    loaded: bool = False


@dataclass
class GitState:
    branch: str = ""
    upstream: str = ""
    ahead: int = 0
    behind: int = 0
    files: dict[str, str] = field(default_factory=dict)      # caminho abs -> letra
    dirs: dict[str, str] = field(default_factory=dict)       # pasta abs -> letra mais forte
    numstat: dict[str, tuple[int, int]] = field(default_factory=dict)
    repo: str = ""


def git_state(root: Path) -> GitState:
    st = GitState()
    try:
        top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True,
                             text=True, timeout=3)
        if top.returncode != 0:
            return st
        st.repo = top.stdout.strip()
        out = subprocess.run(["git", "-C", st.repo, "status", "--porcelain=v1", "-b", "-z", "--untracked-files=all"],
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return st
    parts = out.split("\0")
    i = 0
    rank = {"D": 5, "U": 5, "M": 4, "R": 3, "A": 2, "?": 1}
    while i < len(parts):
        rec = parts[i]
        i += 1
        if not rec:
            continue
        if rec.startswith("## "):
            head = rec[3:]
            br, _, rest = head.partition("...")
            st.branch = br.replace("No commits yet on ", "")
            if rest:
                up, _, ab = rest.partition(" ")
                st.upstream = up
                for tok in ab.strip("[]").split(", "):
                    if tok.startswith("ahead "):
                        st.ahead = int(tok[6:])
                    elif tok.startswith("behind "):
                        st.behind = int(tok[7:])
            continue
        xy, path = rec[:2], rec[3:]
        if xy[0] in "RC":
            i += 1  # o caminho antigo vem no próximo campo
        letter = "?" if xy == "??" else next((c for c in xy if c not in " "), "M")
        letter = {"C": "A", "T": "M"}.get(letter, letter)
        ab = os.path.join(st.repo, path)
        st.files[ab] = letter
        d = os.path.dirname(ab)
        while d.startswith(st.repo) and len(d) >= len(st.repo):
            if rank.get(letter, 0) > rank.get(st.dirs.get(d, ""), 0):
                st.dirs[d] = letter
            if d == st.repo:
                break
            d = os.path.dirname(d)
    try:
        ns = subprocess.run(["git", "-C", st.repo, "diff", "--numstat", "HEAD"], capture_output=True, text=True,
                            timeout=5).stdout
        for line in ns.splitlines():
            a, d_, p = (line.split("\t") + ["", "", ""])[:3]
            if a.isdigit() and d_.isdigit():
                st.numstat[os.path.join(st.repo, p)] = (int(a), int(d_))
    except (OSError, subprocess.TimeoutExpired):
        pass
    return st


def human_size(n: int) -> str:
    for unit in ("B", "K", "M", "G"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}T"


def age(ts: float) -> str:
    d = max(0, time.time() - ts)
    if d < 60:
        return "agora"
    if d < 3600:
        return f"{int(d // 60)}m"
    if d < 86400:
        return f"{int(d // 3600)}h"
    if d < 86400 * 30:
        return f"{int(d // 86400)}d"
    return time.strftime("%d/%m", time.localtime(ts))


class FileTree(Tree[Entry]):
    """Árvore com carga preguiçosa, git status e brilho de atividade no rótulo."""

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
        show_hidden = self.state.show_hidden
        items = [i for i in items if i.name not in IGNORE and (show_hidden or not i.name.startswith(".")
                                                              or i.name in (".github", ".agents", ".gemini"))]
        items.sort(key=lambda i: (not i.is_dir(follow_symlinks=False) and not (i.is_symlink() and i.is_dir()),
                                  i.name.lower()))
        for i in items:
            is_dir = i.is_dir()
            ent = Entry(Path(i.path), is_dir)
            if is_dir:
                node.add(i.name, data=ent, allow_expand=True)
            else:
                node.add_leaf(i.name, data=ent)

    def reload(self, node: TreeNode[Entry]) -> None:
        """Recarrega os filhos de uma pasta mantendo as subpastas abertas."""
        if node.data is None or not node.data.is_dir:
            return
        opened = {str(n.data.path) for n in self._walk(node) if n.data and n.is_expanded and n is not node}
        node.data.loaded = False
        self.load(node)
        for n in list(self._walk(node)):
            if n is not node and n.data and str(n.data.path) in opened:
                self.load(n)
                n.expand()

    def _walk(self, node: TreeNode[Entry]):
        stack = [node]
        while stack:
            n = stack.pop()
            yield n
            stack.extend(n.children)

    def find(self, path: Path, create: bool = True) -> TreeNode[Entry] | None:
        """Acha (abrindo as pastas no caminho) o nó de um caminho dentro da raiz."""
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
                node.data.loaded = False  # arquivo novo: recarrega a pasta
                self.load(node)
                nxt = next((c for c in node.children if c.data and c.data.path.name == part), None)
            if nxt is None:
                return None
            node = nxt
        return node

    def render_label(self, node: TreeNode[Entry], base_style: Style, style: Style) -> Text:
        e = node.data
        if e is None:
            return Text(str(node.label))
        s = self.state
        p = str(e.path)
        name = e.path.name
        git = s.git.dirs.get(p) if e.is_dir else s.git.files.get(p)
        act = s.activity.get(p)
        now = time.time()

        if e.is_dir:
            icon = "▾ " if node.is_expanded else "▸ "
            name_style = Style(color=C["dir"], bold=True)
        else:
            icon = "  "
            name_style = Style(color=C["fg"])
        if git:
            name_style += Style(color=C.get(git, C["M"]))
        if e.path.is_symlink():
            name += " →"
        if e.path.name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
            name += " ✦"

        label = Text(icon, style=Style(color=C["muted"]))
        label.append(name, style=name_style)
        if act:
            kind, ts = act
            a = now - ts
            col = C[kind]
            if a < FLASH:
                # brilho: alterna intensidade enquanto o agente acabou de tocar
                phase = int(a * 4) % 2 == 0
                label.stylize(Style(bgcolor=col if phase else C["sel"], color="#1a1b26" if phase else col,
                                    bold=True), len(icon))
            elif a < GLOW:
                label.append(" ●" if kind != "read" else " ○", style=Style(color=col))
        if git and not e.is_dir:
            label.append(f" {git}", style=Style(color=C.get(git, C["M"]), bold=True))
            ns = s.git.numstat.get(p)
            if ns:
                label.append(f" +{ns[0]}", style=Style(color=C["add"]))
                label.append(f" -{ns[1]}", style=Style(color=C["del"]))
        if s.column != "none" and not e.is_dir:
            try:
                st = e.path.stat()
                extra = age(st.st_mtime) if s.column == "age" else human_size(st.st_size)
            except OSError:
                extra = ""
            if extra:
                depth, n = 0, node.parent
                while n is not None and n is not self.root:
                    depth += 1
                    n = n.parent
                avail = self.size.width - 3 - depth * self.guide_depth
                pad = avail - label.cell_len - len(extra)
                label.append(" " * max(1, pad) + extra, style=Style(color=C["muted"]))
        return label

    def on_resize(self) -> None:
        self._invalidate()


class Preview(VerticalScroll):
    def show(self, path: Path | None) -> None:
        body = self.query_one("#preview-body", Static)
        if path is None:
            body.update("")
            return
        if path.is_dir():
            try:
                kids = list(os.scandir(path))
                n_dir = sum(1 for k in kids if k.is_dir())
                body.update(Text(f"{path.name}/\n\n{n_dir} pastas, {len(kids) - n_dir} arquivos", style=C["muted"]))
            except OSError as exc:
                body.update(str(exc))
            return
        try:
            if path.stat().st_size > 512 * 1024:
                body.update(Text(f"{path.name}: {human_size(path.stat().st_size)}, grande demais para preview",
                                 style=C["muted"]))
                return
            raw = path.read_bytes()
            if b"\0" in raw[:4096]:
                body.update(Text(f"{path.name}: arquivo binário", style=C["muted"]))
                return
            code = raw.decode("utf-8", errors="replace")
            lexer = Syntax.guess_lexer(str(path), code)
            body.update(Syntax(code, lexer, theme="monokai", line_numbers=True, word_wrap=False,
                               background_color="#1a1b26"))
        except OSError as exc:
            body.update(str(exc))
        self.scroll_home(animate=False)

    def compose(self) -> ComposeResult:
        yield Static(id="preview-body")


HELP = """[b #7dcfff]agy-tree[/]  atalhos

  [b]j k[/] ↓ ↑     mover
  [b]l[/] → enter   abrir pasta / preview
  [b]h[/] ←         fechar pasta / subir
  [b]space[/]       abrir ou fechar
  [b]p[/]           preview do arquivo
  [b]o[/]           abrir no editor
  [b]s[/] /         buscar pelo nome
  [b]f[/]           seguir o agente
  [b].[/]           mostrar ocultos
  [b]c[/]           coluna idade/tamanho
  [b]g G[/]         topo / fim
  [b]r[/]           recarregar
  [b]y[/]           copiar caminho
  [b]?[/]           esta ajuda
  [b]q[/]           sair

  [#bb9af7]○ lido[/]  [#ff9e64]● escrito[/]  [#9ece6a]● git[/]
  [#e0af68]M[/] alterado  [#9ece6a]?[/] novo  [#f7768e]D[/] apagado
"""


class AgyTree(App):
    CSS = """
    Screen { background: #1a1b26; color: #c0caf5; }
    #header { height: 1; padding: 0 1; background: #16161e; color: #7aa2f7; }
    #branch { height: 1; padding: 0 1; color: #565f89; }
    #body { height: 1fr; }
    FileTree { background: #1a1b26; padding: 0 0 0 1; scrollbar-size-vertical: 1; }
    FileTree > .tree--cursor { background: #283457; }
    FileTree > .tree--guides { color: #3b4261; }
    FileTree > .tree--guides-hover { color: #565f89; }
    FileTree > .tree--guides-selected { color: #7aa2f7; }
    Preview { height: 45%; border-top: solid #3b4261; display: none; background: #1a1b26; }
    Preview.on { display: block; }
    #search { display: none; margin: 0 1; border: tall #3b4261; background: #16161e; }
    #search.on { display: block; }
    #results { display: none; height: 40%; background: #16161e; border: none; }
    #results.on { display: block; }
    #help { display: none; padding: 1 2; background: #16161e; height: 1fr; }
    #help.on { display: block; }
    #footer { height: 1; padding: 0 1; background: #16161e; color: #565f89; }
    """
    BINDINGS = [
        Binding("q", "quit", "sair"),
        Binding("j", "cursor_down", show=False), Binding("k", "cursor_up", show=False),
        Binding("h", "collapse", show=False), Binding("left", "collapse", show=False),
        Binding("l", "expand", show=False), Binding("right", "expand", show=False),
        Binding("g", "top", show=False), Binding("G", "bottom", show=False),
        Binding("p", "preview", show=False), Binding("f", "follow", show=False),
        Binding("s", "search", show=False), Binding("slash", "search", show=False),
        Binding("full_stop", "hidden", show=False), Binding("c", "column", show=False),
        Binding("r", "refresh", show=False), Binding("o", "open", show=False),
        Binding("y", "copy", show=False), Binding("question_mark", "help", show=False),
        Binding("escape", "escape", show=False),
    ]

    def __init__(self, root: Path, activity_file: str | None) -> None:
        super().__init__()
        self.root_path = root.resolve()
        self.git = GitState()
        self.activity: dict[str, tuple[str, float]] = {}
        self.activity_files = [activity_file] if activity_file else ACTIVITY_DEFAULT
        self.offsets: dict[str, int] = {}
        self.follow = True
        self.show_hidden = False
        self.column = "age"
        self.last_cmd = ""
        self.last_touch = ""

    def compose(self) -> ComposeResult:
        yield Static(id="header")
        yield Static(id="branch")
        yield Input(placeholder="buscar arquivo pelo nome…", id="search")
        yield OptionList(id="results")
        with Vertical(id="body"):
            yield FileTree(self.root_path, self)
            yield Static(HELP, id="help")
            yield Preview()
        yield Static(id="footer")

    @property
    def tree(self) -> FileTree:
        return self.query_one(FileTree)

    def on_mount(self) -> None:
        t = self.tree
        t.load(t.root)
        t.root.expand()
        t.focus()
        t.cursor_line = 0
        # começa a ler o activity do fim: só mostra o que o agente fizer daqui em diante
        for f in self.activity_files:
            try:
                self.offsets[f] = os.path.getsize(f)
            except OSError:
                self.offsets[f] = 0
        self.refresh_git()
        self.set_interval(0.25, self.tick)
        self.set_interval(3.0, self.refresh_git)
        self.update_chrome()

    # ---------- dados ----------
    @work(thread=True, exclusive=True, group="git")
    def refresh_git(self) -> None:
        st = git_state(self.root_path)
        self.call_from_thread(self._set_git, st)

    def _set_git(self, st: GitState) -> None:
        self.git = st
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
            if size < off:      # arquivo girado
                off = 0
            if size == off:
                continue
            with open(f, encoding="utf-8", errors="replace") as fh:
                fh.seek(off)
                chunk = fh.read()
            self.offsets[f] = off + len(chunk.encode("utf-8"))
            for line in chunk.splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    pass
        return events

    def tick(self) -> None:
        root = str(self.root_path)
        changed = False
        git_dirty = False
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
                self.activity[p] = (kind if kind in ("read", "write", "git") else "read", ev.get("t", time.time()))
                self.last_touch = f"{'lendo' if kind == 'read' else 'escrevendo' if kind == 'write' else 'git'} " \
                                  f"{os.path.relpath(p, root)}"
                if kind in ("write", "git"):
                    git_dirty = True
                    parent = self.tree.find(Path(p).parent, create=self.follow) if p != root else None
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
                self.tree.scroll_to_node(node, animate=False)
        # apaga marcas antigas e redesenha enquanto houver brilho
        now = time.time()
        old = [k for k, (_, ts) in self.activity.items() if now - ts > GLOW]
        for k in old:
            del self.activity[k]
        if changed or old or any(now - ts < GLOW for _, ts in self.activity.values()):
            self.tree._invalidate()
            self.tree.refresh()
            self.update_chrome()

    # ---------- interface ----------
    def update_chrome(self) -> None:
        home = os.path.expanduser("~")
        root = str(self.root_path)
        shown = "~" + root[len(home):] if root.startswith(home) else root
        flags = []
        if self.follow:
            flags.append("seguindo")
        if self.show_hidden:
            flags.append("ocultos")
        self.query_one("#header", Static).update(
            Text.assemble(("agy-tree ", "bold #7dcfff"), (shown, "#c0caf5"),
                          ("  " + " · ".join(flags), "#565f89") if flags else ""))
        g = self.git
        if g.branch:
            b = Text.assemble(("⎇ ", "#9ece6a"), (g.branch, "bold #9ece6a"))
            if g.ahead:
                b.append(f" ↑{g.ahead}", style="#e0af68")
            if g.behind:
                b.append(f" ↓{g.behind}", style="#f7768e")
            n = len(g.files)
            if n:
                b.append(f"  {n} alterado{'s' if n > 1 else ''}", style="#565f89")
        else:
            b = Text("sem git", style="#565f89")
        self.query_one("#branch", Static).update(b)
        foot = Text()
        if self.last_touch:
            foot.append(self.last_touch, style="#bb9af7")
        if self.last_cmd:
            if foot:
                foot.append("  ")
            foot.append("$ " + self.last_cmd.splitlines()[0][:120], style="#565f89")
        if not foot:
            foot = Text("? atalhos · aguardando o agente…", style="#565f89")
        self.query_one("#footer", Static).update(foot)

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
        if e and not e.is_dir:
            pv = self.query_one(Preview)
            pv.add_class("on")
            pv.show(e.path)

    def action_cursor_down(self) -> None:
        self.tree.action_cursor_down()

    def action_cursor_up(self) -> None:
        self.tree.action_cursor_up()

    def action_expand(self) -> None:
        node = self.tree.cursor_node
        if node and node.data and node.data.is_dir:
            self.tree.load(node)
            if node.is_expanded and node.children:
                self.tree.move_cursor(node.children[0])
            node.expand()

    def action_collapse(self) -> None:
        node = self.tree.cursor_node
        if node is None:
            return
        if node.is_expanded and node.data and node.data.is_dir:
            node.collapse()
        elif node.parent is not None and node.parent is not self.tree.root:
            self.tree.move_cursor(node.parent)
            node.parent.collapse()

    def action_top(self) -> None:
        self.tree.action_scroll_home()
        self.tree.cursor_line = 0

    def action_bottom(self) -> None:
        self.tree.action_scroll_end()
        self.tree.cursor_line = self.tree.last_line

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
        self.column = {"age": "size", "size": "none", "none": "age"}[self.column]
        self.tree._invalidate()
        self.tree.refresh()

    def action_refresh(self) -> None:
        self.tree.reload(self.tree.root)
        self.refresh_git()

    def action_help(self) -> None:
        self.query_one("#help").toggle_class("on")
        self.tree.display = not self.query_one("#help").has_class("on")

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
        box = self.query_one("#search", Input)
        box.add_class("on")
        box.value = ""
        box.focus()

    def action_escape(self) -> None:
        for w in ("#search", "#results", "#help", "Preview"):
            self.query_one(w).remove_class("on")
        self.tree.display = True
        self.tree.focus()

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
            dirnames[:] = [d for d in dirnames if d not in IGNORE and (self.show_hidden or not d.startswith("."))]
            for name in dirnames + filenames:
                if q in name.lower():
                    hits.append(os.path.relpath(os.path.join(dirpath, name), self.root_path))
                    if len(hits) >= 200:
                        break
            if len(hits) >= 200:
                break
        hits.sort(key=lambda h: (not os.path.basename(h).lower().startswith(q), len(h)))
        res.add_options([Option(h, id=h) for h in hits[:100]])
        res.set_class(bool(hits), "on")

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
        # setas no campo de busca andam na lista de resultados
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
