"""Hook SessionStart do agy-turbo.

1. Primeira sessão (ou versão nova do plugin): roda o bootstrap em segundo plano.
2. Dentro do tmux: abre o agy-tree ao lado.
3. Há um HANDOFF.md recente e ainda não usado na pasta: injeta como contexto da conversa nova.
"""
import hashlib
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

HANDOFF_MAX_AGE = 48 * 3600


def maybe_bootstrap():
    st = common.load("bootstrap.json")
    if st.get("version") == common.version() and st.get("ok"):
        return
    if st.get("running_since", 0) > time.time() - 600:
        return
    subprocess.Popen([sys.executable, "-I", os.path.join(common.ROOT, "hooks", "bootstrap.py")],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True, env=dict(os.environ, AGY_TURBO_DATA=common.DATA))


def handoff_step(cwd):
    f = os.path.join(cwd, "HANDOFF.md")
    try:
        st = os.stat(f)
    except OSError:
        return None
    if time.time() - st.st_mtime > HANDOFF_MAX_AGE:
        return None
    used = common.load("handoffs.json")
    key = hashlib.sha1(f"{f}:{st.st_mtime}".encode()).hexdigest()
    if key in used:
        return None
    with open(f, encoding="utf-8", errors="replace") as fh:
        text = fh.read()[:20000]
    used[key] = {"path": f, "t": time.time()}
    common.save("handoffs.json", used)
    return {"systemMessage": {"systemMessage": (
        "This conversation continues earlier work. The previous session wrote this handoff (HANDOFF.md in the "
        "workspace). Use it as context; confirm the next step with the user before large changes.\n\n" + text)}}


def main():
    raw = sys.stdin.read()
    if common.nested_judge():
        return {}
    try:
        ev = json.loads(raw or "{}")
    except ValueError:
        ev = {}
    out = {}
    try:
        maybe_bootstrap()
    except Exception:
        pass
    try:
        import open_tree
        open_tree.open_tree(ev)
    except Exception:
        pass
    try:
        cwd = ev.get("cwd") or (ev.get("workspacePaths") or [os.getcwd()])[0]
        step = handoff_step(cwd)
        if step:
            out["injectSteps"] = [step]
    except Exception:
        pass
    return out


if __name__ == "__main__":
    print(json.dumps(main()))
