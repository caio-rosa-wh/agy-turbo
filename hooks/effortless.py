"""effortless para o agy: esforço automático, compact e handoff, sem travar suas mensagens.

Inspirado no HeyCubit/effortless (MIT), reimplementado para os hooks do agy.

Fluxo (o agy roda no tmux, que é como o agy-turbo abre; sem tmux só há sugestões na statusline):
  Você envia (PreInvocation, 1ª chamada)  -> regras locais, na hora (0 s):
      pedido explícito ("max effort", "esforço alto") ou sinal claro de tarefa pesada com esforço baixo
      -> sobe já: digita `/effort X`, reenvia a mensagem e encerra esta chamada.
      continuação curta ("ok", "segue") -> mantém.
  Em paralelo, o juiz LLM (Flash via `agy -p`) avalia a mensagem em segundo plano:
      pede mais esforço e o turno ainda roda -> digita `/effort X`: as próximas chamadas do turno já sobem.
      pede menos -> fica para o fim do turno.     troca de assunto com contexto grande -> recomenda /handoff.
  Fim do turno (Stop):
      desce o esforço pendente; contexto >= compact_at com compact=auto -> digita `/compact`;
      handoff recomendado -> aviso na statusline (handoff=auto digita /handoff).

Estado em effortless.json; configuração em config.json (agy-effortless).
"""
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

LEVELS = common.LEVELS
DEFAULTS = {"auto": True, "judge": "flash", "judge_model": "gemini-3.8-flash-low", "judge_timeout": 20,
            "floor": "low", "ceiling": "max", "bias": 0, "economy": False, "resubmit": True,
            "compact": "auto", "compact_at": 80, "handoff": "suggest", "handoff_at": 40}
CONTINUE = {"ok", "okay", "sim", "s", "yes", "y", "go", "segue", "seguir", "continua", "continue", "pode",
            "manda", "vai", "beleza", "blz", "isso", "certo", "faz", "faça", "bora", "next", "proceed", "valeu",
            "obrigado", "thanks", "perfeito", "show", "top"}
EXPLICIT = [
    (r"\b(max(imum)?|m[aá]xim[oa])\s+(effort|esfor[cç]o)|\b(effort|esfor[cç]o)\s*[:=]?\s*(max|m[aá]xim[oa])", "max"),
    (r"\bxhigh\b|\b(extra|muito)\s+(alto|high)\b", "xhigh"),
    (r"\b(high|alto|alta)\s+(effort|esfor[cç]o)|\b(effort|esfor[cç]o)\s*[:=]?\s*(high|alto|alta)\b|\bpense\s+bem\b|"
     r"\bthink\s+hard\b|\bultrathink\b", "high"),
    (r"\b(medium|m[eé]dio|media)\s+(effort|esfor[cç]o)|\b(effort|esfor[cç]o)\s*[:=]?\s*(medium|m[eé]dio)\b", "medium"),
    (r"\b(low|baixo|baixa)\s+(effort|esfor[cç]o)|\b(effort|esfor[cç]o)\s*[:=]?\s*(low|baixo|baixa)\b|\bsem\s+pensar\b",
     "low"),
]
HEAVY = re.compile(r"\b(arquitetura|architecture|refator|refactor|migra|migrat|debug|investig|por que|why|race|"
                   r"seguran[cç]a|security|performance|otimiz|optimi|design|plano|plan|revis|review|prova|proof|"
                   r"concorr|deadlock|vazamento|leak|produ[cç][aã]o|production|incidente|incident)", re.I)
LIGHT = re.compile(r"^(qual|quanto|quantos|o que [eé]|what is|how many|lista|list|mostra|show|renomeia|rename|"
                   r"traduz|translate|formata|format|diga|say|oi|ol[aá]|hello|hi)\b", re.I)


def cfg():
    c = dict(DEFAULTS)
    c.update(common.load("config.json"))
    return c


def split_model(model_name):
    base, _, lvl = (model_name or "").rpartition("-")
    return (base, lvl) if lvl in LEVELS else (model_name or "", "")


def available(base):
    lv = (common.load("models.json").get("levels") or {}).get(base)
    return lv or ["low", "medium", "high"]


def clamp(level, levels):
    if level in levels:
        return level
    i = LEVELS.index(level)
    return min(levels, key=lambda l: abs(LEVELS.index(l) - i))


def limits(level, levels, c, conf=1.0):
    i = LEVELS.index(level)
    bias = int(c.get("bias") or 0)
    if bias and conf < (0.65 if abs(bias) == 1 else 0.85):
        i += 1 if bias > 0 else -1
    i = max(LEVELS.index(c["floor"]), min(LEVELS.index(c["ceiling"]), i))
    if c.get("economy"):
        i = min(i, LEVELS.index("medium"))
    return clamp(LEVELS[max(0, min(i, len(LEVELS) - 1))], levels)


def last_reply(transcript):
    try:
        with open(transcript, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 200_000))
            lines = f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "PLANNER_RESPONSE" and d.get("content"):
            return d["content"][-1500:]
    return ""


def context_pct():
    sl = common.load("statusline.json")
    try:
        return float((sl.get("context_window") or {}).get("used_percentage") or 0)
    except (TypeError, ValueError):
        return 0.0


# ---------- decisão local (instantânea) ----------
def local(msg, current, levels, c):
    """(nível, motivo, forte). forte = agir já sem esperar o juiz."""
    low = msg.strip().lower()
    for pat, lvl in EXPLICIT:
        if re.search(pat, low):
            return clamp(lvl, levels), "você pediu " + lvl, True
    words = re.findall(r"[\wà-ú]+", low)
    if current and words and len(words) <= 4 and all(w in CONTINUE for w in words):
        return current, "continuação: mantém", False
    if HEAVY.search(msg) or len(words) > 120:
        lvl = limits("high", levels, c)
        strong = current == "low" and LEVELS.index(lvl) > LEVELS.index(current)
        return lvl, "tarefa pesada", strong
    if LIGHT.search(msg.strip()) or len(words) <= 8:
        return limits("low", levels, c), "pedido simples", False
    return limits("medium", levels, c), "tarefa comum", False


# ---------- juiz LLM (em segundo plano) ----------
def judge(msg, current, levels, reply, ctx, c):
    agy = shutil.which("agy")
    if not agy:
        return None
    prompt = (
        "You pick the reasoning effort for a coding agent's turn. Levels, cheapest first: "
        f"{', '.join(levels)}. Current level: {current or 'unknown'}.\n"
        "Use the lowest level that will still do the job well: low for lookups, small edits, short answers and "
        "simple commands; medium for ordinary coding; high for debugging, multi-file changes, design and review; "
        "higher only for hard reasoning. A short reply that approves or continues a plan inherits the size of "
        "the work it approves (read the previous answer). topic_change: true if the new message starts a task "
        "unrelated to the previous answer.\n"
        'Reply with ONE line of JSON and nothing else: {"effort": "<level>", "confidence": <0..1>, '
        '"reason": "<at most 8 words, in the user\'s language>", "topic_change": <true|false>}\n\n'
        f"Previous assistant answer (tail):\n<<<\n{reply[-1500:]}\n>>>\n\nUser message:\n<<<\n{msg[:2000]}\n>>>")
    try:
        r = subprocess.run([agy, "-p", prompt, "--model", c["judge_model"], "--output-format", "json",
                            "--disable-slash-commands", "--print-timeout", f"{int(c['judge_timeout'])}s"],
                           capture_output=True, text=True, timeout=int(c["judge_timeout"]) + 5, cwd=common.DATA,
                           env=dict(os.environ, AGY_TURBO_JUDGE="1", AGY_TREE="0", NO_COLOR="1"))
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_verdict(r.stdout, levels)


def parse_verdict(stdout, levels):
    """Aceita a saída JSON do `agy -p` (structured_output ou response) e pega o último objeto válido."""
    texts = []
    try:
        d = json.loads(stdout)
        if isinstance(d.get("structured_output"), dict):
            texts.append(json.dumps(d["structured_output"]))
        texts.append(d.get("response") or "")
    except (ValueError, AttributeError):
        texts.append(stdout or "")
    for text in texts:
        for m in reversed(list(re.finditer(r"\{[^{}]*\}", text))):
            try:
                v = json.loads(m.group(0))
            except ValueError:
                continue
            if v.get("effort") in levels:
                try:
                    conf = float(v.get("confidence") if v.get("confidence") is not None else 0.7)
                except (TypeError, ValueError):
                    conf = 0.7
                return v["effort"], conf, str(v.get("reason") or "")[:60], bool(v.get("topic_change"))
    return None


# ---------- tmux ----------
def pane():
    return os.environ.get("TMUX_PANE") if os.environ.get("TMUX") else None


def tmux_type(target, *items, delay=0.0):
    """Digita no painel do agy num processo separado (o hook já pode ter retornado)."""
    cmds = [f"sleep {float(delay)}"] if delay else ["true"]
    q = shlex.quote(target)
    for kind, val in items:
        if kind == "keys":
            cmds.append(f"tmux send-keys -t {q} -l -- {shlex.quote(val)}")
        elif kind == "enter":
            cmds.append(f"tmux send-keys -t {q} Enter")
        elif kind == "altm":   # o agy põe a mensagem na fila enquanto encerra o turno; alt+m envia na hora
            cmds.append(f"tmux send-keys -t {q} M-m")
        elif kind == "paste":
            cmds.append(f"printf %s {shlex.quote(val)} | tmux load-buffer -b agyturbo - && "
                        f"tmux paste-buffer -p -d -b agyturbo -t {q}")
        elif kind == "sleep":
            cmds.append(f"sleep {float(val)}")
    subprocess.Popen(["sh", "-c", " && ".join(cmds)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def set_effort(target, lvl, delay=0.0):
    tmux_type(target, ("keys", f"/effort {lvl}"), ("enter", None), delay=delay)


# ---------- hooks ----------
def pre_invocation(ev):
    if ev.get("invocationNum") not in (0, None):
        return {}
    c = cfg()
    msg = ev.get("lastUserInput") or ""
    base, current = split_model(ev.get("modelName"))
    levels = available(base)
    state = common.load("effortless.json")
    state.update({"model": base, "current": current, "levels": levels, "auto": c["auto"], "t_seen": time.time()})
    h = hashlib.sha1(msg.encode()).hexdigest()
    rs = state.get("resubmit") or {}
    if rs.get("hash") == h and time.time() - rs.get("t", 0) < 180:
        state.pop("resubmit", None)          # a mensagem que nós mesmos reenviamos: já está no nível certo
        state.update({"turn": h, "turn_active": True})
        common.save("effortless.json", state)
        return {}
    if not c["auto"] or not msg.strip() or msg.lstrip().startswith("/") or not current:
        common.save("effortless.json", state)
        return {}
    lvl, why, strong = local(msg, current, levels, c)
    state.update({"decided": lvl, "reason": why, "source": "local", "t": time.time(), "pending": None,
                  "turn": h, "turn_active": True, "judge": None, "raised_mid_turn": False})
    if state.get("hint") == "handoff":
        state["hint"] = None
    target = pane()
    out = {}
    if lvl != current:
        up = LEVELS.index(lvl) > LEVELS.index(current)
        if not target:
            state["suggest"] = lvl
        elif up and strong and c["resubmit"]:
            state["resubmit"] = {"hash": h, "t": time.time(), "to": lvl}
            items = [("keys", f"/effort {lvl}"), ("enter", None), ("sleep", "0.4")]
            items += [("paste", msg)] if "\n" in msg else [("keys", msg)]
            items += [("sleep", "0.2"), ("enter", None), ("sleep", "0.6"), ("altm", None)]
            tmux_type(target, *items, delay=0.5)
            state["turn_active"] = False
            out = {"terminationBehavior": "terminate"}
        elif not up:
            state["pending"] = lvl            # descer só no fim do turno
        if target:
            state.pop("suggest", None)
    else:
        state.pop("suggest", None)
    common.save("effortless.json", state)
    # juiz em segundo plano: não segura a mensagem (e não roda quando já vamos reenviar)
    if not out and c["judge"] == "flash" and not strong:
        common.save("judge-job.json", {"msg": msg, "current": current, "levels": levels, "turn": h,
                                       "transcript": ev.get("transcriptPath") or "", "pane": target})
        subprocess.Popen([sys.executable, "-I", os.path.abspath(__file__), "--judge"], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                         env=dict(os.environ, AGY_TURBO_DATA=common.DATA))
    return out


def run_judge():
    job = common.load("judge-job.json")
    if not job:
        return
    c = cfg()
    t0 = time.time()
    v = judge(job["msg"], job["current"], job["levels"], last_reply(job["transcript"]), context_pct(), c)
    state = common.load("effortless.json")
    if state.get("turn") != job["turn"]:
        return                                # já chegou outra mensagem: veredito velho
    ms = int((time.time() - t0) * 1000)
    if not v:
        state["judge"] = {"ok": False, "ms": ms}
        common.save("effortless.json", state)
        return
    lvl, conf, why, topic = v
    lvl = limits(lvl, job["levels"], c, conf)
    cur = state.get("current") or job["current"]
    state["judge"] = {"ok": True, "ms": ms, "effort": lvl, "conf": conf, "reason": why}
    state.update({"decided": lvl, "reason": why, "source": "flash"})
    if topic and context_pct() >= c["handoff_at"] and c["handoff"] != "off":
        state["hint"] = "handoff"
    if conf >= 0.5 and cur and lvl != cur:
        if LEVELS.index(lvl) > LEVELS.index(cur):
            state["pending"] = None
            if state.get("turn_active") and job.get("pane"):
                set_effort(job["pane"], lvl)  # o turno ainda roda: as próximas chamadas já sobem
                state["current"] = lvl
                state["raised_mid_turn"] = True
            elif not job.get("pane"):
                state["suggest"] = lvl
        else:
            state["pending"] = lvl
    elif cur and lvl == cur:
        state["pending"] = None
    common.save("effortless.json", state)


def stop(ev):
    if ev.get("terminationReason") == "TERMINAL_CUSTOM_HOOK":
        return {}                              # é o nosso reenvio
    c = cfg()
    state = common.load("effortless.json")
    state["turn_active"] = False
    target = pane()
    items = []
    lvl = state.get("pending")
    if lvl and target:
        items += [("keys", f"/effort {lvl}"), ("enter", None), ("sleep", "0.5")]
        state["current"], state["pending"] = lvl, None
    ctx = context_pct()
    if ctx >= c["compact_at"]:
        if c["compact"] == "auto" and target and time.time() - state.get("compact_t", 0) > 300:
            items += [("keys", "/compact"), ("enter", None)]
            state["compact_t"] = time.time()
            state["hint"] = "compacting"
        elif c["compact"] != "off":
            state["hint"] = "compact"
    elif state.get("hint") == "handoff" and c["handoff"] == "auto" and target \
            and time.time() - state.get("handoff_t", 0) > 600:
        items += [("keys", "/handoff"), ("enter", None)]
        state["handoff_t"] = time.time()
    elif state.get("hint") in ("compacting", "compact"):
        state["hint"] = None
    if items:
        tmux_type(target, *items, delay=0.3)
    common.save("effortless.json", state)
    return {}


def main():
    if "--judge" in sys.argv:
        run_judge()
        return None
    raw = sys.stdin.read()
    if common.nested_judge():
        return {}
    try:
        ev = json.loads(raw or "{}")
    except ValueError:
        return {}
    name = ev.get("hookEventName")
    if name == "PreInvocation":
        return pre_invocation(ev)
    if name == "Stop":
        return stop(ev)
    return {}


if __name__ == "__main__":
    try:
        out = main()
        if out is not None:
            print(json.dumps(out))
    except Exception:
        if "--judge" not in sys.argv:
            print("{}")
