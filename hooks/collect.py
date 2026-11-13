"""Hook PostToolUse do agy: grava em activity.jsonl os arquivos que o agente leu, escreveu ou tocou via git.

Precisa ser rápido (hooks travam o agente): só biblioteca padrão, sem subprocessos, e sempre responde "{}".
Uma linha por evento: {"t", "conv", "cwd", "kind": "read"|"write"|"git"|"cmd", "paths": [...], "cmd"?, "tool"}.
"""
import json
import os
import shlex
import sys
import time

READ_TOOLS = {"read_file", "view_file", "view_file_outline", "view_code_item", "list_dir", "find_by_name",
              "grep_search", "codebase_search", "read_notebook"}
WRITE_TOOLS = {"write_file", "edit_file", "replace_file_content", "multi_replace_file_content", "write_to_file",
               "edit_notebook", "delete_file"}
# comandos de shell que só leem / que escrevem nos caminhos passados
READERS = {"cat", "bat", "head", "tail", "less", "more", "grep", "rg", "ag", "find", "fd", "ls", "tree", "wc",
           "file", "stat", "diff", "jq", "awk", "cut", "sort", "uniq", "nl", "od", "xxd", "md5sum", "sha256sum"}
WRITERS = {"touch", "rm", "mv", "cp", "mkdir", "rmdir", "tee", "truncate", "chmod", "ln", "install"}
MAX_BYTES = 5 * 1024 * 1024


def data_dir():
    d = os.environ.get("PLUGIN_DATA") or os.environ.get("AGY_TURBO_DATA") or os.path.expanduser("~/.gemini/antigravity-cli/plugin_data/agy-turbo")
    os.makedirs(d, exist_ok=True)
    return d


def tool_paths(args):
    out = []
    for k in ("Path", "AbsolutePath", "TargetFile", "File", "DirectoryPath", "SearchDirectory", "SearchPath"):
        v = args.get(k)
        if isinstance(v, str) and v:
            out.append(v)
    return out


def shell_events(cmdline, cwd):
    """Classifica um CommandLine em eventos read/write/git, achando os argumentos que são caminhos reais."""
    events = []
    for part in cmdline.replace("&&", ";").replace("||", ";").replace("|", ";").split(";"):
        try:
            toks = shlex.split(part, posix=True)
        except ValueError:
            continue
        # tira prefixos como "sudo", "env X=1", "timeout 5"
        while toks and (toks[0] in ("sudo", "env", "command", "nice", "time") or "=" in toks[0].split("/")[0]):
            toks = toks[1:]
        if not toks:
            continue
        prog = os.path.basename(toks[0])
        redirect_out = [toks[i + 1] for i, t in enumerate(toks[:-1]) if t in (">", ">>")]
        redirect_out += [t[1:].lstrip(">") for t in toks if t.startswith(">") and len(t) > 1 and t not in (">>",)]
        paths = []
        for t in toks[1:]:
            if t.startswith("-") or t in (">", ">>", "<"):
                continue
            p = t if os.path.isabs(t) else os.path.join(cwd, t)
            # rm/mv rodam antes do hook: o arquivo pode já não existir, basta a pasta existir
            if os.path.exists(p) or (prog in WRITERS and os.path.isdir(os.path.dirname(os.path.normpath(p)))):
                paths.append(os.path.normpath(p))
        if prog == "git":
            events.append(("git", paths, part.strip()))
        elif prog == "sed" and any(t == "-i" or t.startswith("-i") for t in toks):
            events.append(("write", paths, None))
        elif prog in WRITERS:
            events.append(("write", paths, None))
        elif prog in READERS or prog == "sed":
            events.append(("read", paths, None))
        if redirect_out:
            events.append(("write", [os.path.normpath(p if os.path.isabs(p) else os.path.join(cwd, p))
                                     for p in redirect_out if p], None))
    return events


def main():
    raw = sys.stdin.read()
    if os.environ.get("AGY_TURBO_JUDGE") == "1":
        print("{}")
        return
    try:
        ev = json.loads(raw or "{}")
    except ValueError:
        print("{}")
        return
    call = ev.get("toolCall") or {}
    name, args = call.get("name") or "", call.get("args") or {}
    cwd = ev.get("cwd") or (ev.get("workspacePaths") or [os.getcwd()])[0]
    base = {"t": round(time.time(), 3), "conv": ev.get("conversationId", ""), "cwd": cwd, "tool": name}
    if ev.get("error"):
        base["error"] = True
    lines = []
    if name in READ_TOOLS:
        lines.append(dict(base, kind="read", paths=tool_paths(args)))
    elif name in WRITE_TOOLS:
        lines.append(dict(base, kind="write", paths=tool_paths(args)))
    elif name == "run_command":
        cmd = args.get("CommandLine") or ""
        for kind, paths, gitcmd in shell_events(cmd, args.get("Cwd") or cwd):
            lines.append(dict(base, kind=kind, paths=paths, **({"cmd": gitcmd} if gitcmd else {})))
        lines.append(dict(base, kind="cmd", paths=[], cmd=cmd[:300]))
    else:
        p = tool_paths(args)
        if p:
            lines.append(dict(base, kind="read", paths=p))
    lines = [l for l in lines if l["paths"] or l["kind"] in ("git", "cmd")]
    if lines:
        f = os.path.join(data_dir(), "activity.jsonl")
        try:
            if os.path.getsize(f) > MAX_BYTES:
                os.replace(f, f + ".1")
        except OSError:
            pass
        with open(f, "a", encoding="utf-8") as out:
            for line in lines:
                out.write(json.dumps(line, ensure_ascii=False) + "\n")
    print("{}")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # um hook com erro não pode atrapalhar o agente
        print("{}")
