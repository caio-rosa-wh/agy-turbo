"""Caminhos e utilidades comuns dos hooks do agy-turbo."""
import json
import os
import tempfile

ROOT = os.environ.get("PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = (os.environ.get("PLUGIN_DATA") or os.environ.get("AGY_TURBO_DATA")
        or os.path.expanduser("~/.gemini/antigravity-cli/plugin_data/agy-turbo"))
LEVELS = ["low", "medium", "high", "xhigh", "max"]
_LOCAL_BIN = os.path.expanduser("~/.local/bin")
if _LOCAL_BIN not in os.environ.get("PATH", "").split(os.pathsep):
    os.environ["PATH"] = _LOCAL_BIN + os.pathsep + os.environ.get("PATH", "")


def nested_judge() -> bool:
    """True dentro da chamada `agy -p` do juiz: os hooks não fazem nada (evita recursão)."""
    return os.environ.get("AGY_TURBO_JUDGE") == "1"


def path(name: str) -> str:
    os.makedirs(DATA, exist_ok=True)
    return os.path.join(DATA, name)


def load(name: str, default=None):
    try:
        with open(path(name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {} if default is None else default


def save(name: str, obj) -> None:
    p = path(name)
    fd, tmp = tempfile.mkstemp(dir=DATA, prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def version() -> str:
    try:
        with open(os.path.join(ROOT, "plugin.json"), encoding="utf-8") as f:
            return json.load(f).get("version", "0")
    except (OSError, ValueError):
        return "0"
