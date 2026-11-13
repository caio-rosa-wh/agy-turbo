"""effortless para o agy: escolhe o esforço de raciocínio de cada mensagem e troca sozinho.

Inspirado no HeyCubit/effortless (MIT), reimplementado para os hooks do agy:
  PreInvocation (1ª chamada de cada mensagem): decide o nível.
    - pedido explícito ("max effort", "esforço alto")      -> esse nível
    - continuação curta ("ok", "segue", "pode")            -> mantém
    - senão: juiz LLM (Flash via `agy -p`, saída JSON)     -> nível + confiança + motivo
    - confiança < 0.5 mantém; aplica viés, piso, teto e modo economia
  Aplicar (precisa do agy rodando no tmux, que é como o agy-turbo abre):
    - subir: digita `/effort X`, reenvia a mensagem e encerra a chamada atual (vale já)
    - descer: guarda e digita `/effort X` no fim do turno (Stop), sem enfraquecer o trabalho em andamento
  Sem tmux: só mostra a sugestão na statusline.

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
DEFAULTS = {"auto": True, "judge": "flash", "judge_model": "gemini-3.8-flash-low", "floor": "low",
            "ceiling": "max", "bias": 0, "economy": False, "resubmit": True, "judge_timeout": 15}
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


def last_reply(transcript):
    """Últimos ~1500 caracteres da última resposta do modelo no transcript do agy."""
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


def local_verdict(msg, current):
    words = len(msg.split())
    if HEAVY.search(msg) or words > 120:
        return "high", 0.6, "local: tarefa pesada"
    if LIGHT.search(msg.strip()) or words <= 8:
        return "low", 0.6, "local: pedido simples"
    return "medium", 0.55, "local: tarefa comum"


def judge(msg, current, levels, reply, ctx, c):
    agy = shutil.which("agy")
    if not agy:
        return None
    schema = {"type": "object", "properties": {
        "effort": {"type": "string", "enum": levels},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
        "handoff": {"type": "boolean"}}, "required": ["effort", "confidence", "reason"]}
    prompt = (
        "You pick the reasoning effort for a coding agent's next turn. Levels, cheapest first: "
        f"{', '.join(levels)}. Current level: {current or 'unknown'}.\n"
        "Use the lowest level that will still do the job well: low for lookups, small edits, short answers and "
        "simple commands; medium for ordinary coding; high for debugging, multi-file changes, design and review; "
        "higher only for hard reasoning. A short reply that approves or continues a plan inherits the size of "
        "the work it approves (read the previous answer). confidence is 0..1. reason: at most 8 words, same "
        f"language as the user. handoff: true only if the new message starts an unrelated task and the context "
        f"is above 30% (it is {ctx:.0f}%).\n\n"
        f"Previous assistant answer (tail):\n<<<\n{reply[-1500:]}\n>>>\n\nUser message:\n<<<\n{msg[:2000]}\n>>>\n"
        "Answer only with the JSON object.")
    try:
        r = subprocess.run([agy, "-p", prompt, "--model", c["judge_model"], "--output-format", "json",
                            "--json-schema", json.dumps(schema), "--disable-slash-commands",
                            "--print-timeout", f"{int(c['judge_timeout'])}s"],
                           capture_output=True, text=True, timeout=int(c["judge_timeout"]) + 4, cwd=common.DATA,
                           env=dict(os.environ, AGY_TURBO_JUDGE="1", AGY_TREE="0", NO_COLOR="1"))
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = r.stdout
    try:
        text = json.loads(text).get("response", text)
    except (ValueError, AttributeError):
        pass
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        v = json.loads(m.group(0))
    except ValueError:
        return None
    if v.get("effort") not in levels:
        return None
    return v["effort"], float(v.get("confidence") or 0), "Flash: " + str(v.get("reason") or "")[:60], \
        bool(v.get("handoff"))


def decide(msg, current, levels, ev, c):
    """(nível, motivo, fonte, handoff)."""
    text = msg.strip()
    low = text.lower()
    for pat, lvl in EXPLICIT:
        if re.search(pat, low):
            return clamp(lvl, levels), "pedido explícito", "explicit", False
    words = re.findall(r"[\wà-ú]+", low)
    if current and words and len(words) <= 4 and all(w in CONTINUE for w in words):
        return current, "continuação curta: mantém", "continue", False
    handoff = False
    v = None
    if c["judge"] == "flash":
        v = judge(text, current, levels, last_reply(ev.get("transcriptPath") or ""), context_pct(), c)
    if v:
        lvl, conf, why, handoff = v
        source = "flash"
    else:
        lvl, conf, why = local_verdict(text, current)
        source = "local"
        if c["judge"] == "flash":
            why += " (juiz sem resposta)"
    if current and conf < 0.5:
        return current, why + " · incerto: mantém", source, handoff
    i = LEVELS.index(lvl)
    bias = int(c.get("bias") or 0)
    if bias and conf < (0.65 if abs(bias) == 1 else 0.85):
        i += 1 if bias > 0 else -1
    i = max(LEVELS.index(c["floor"]), min(LEVELS.index(c["ceiling"]), i))
    if c.get("economy"):
        i = min(i, LEVELS.index("medium"))
    return clamp(LEVELS[max(0, min(i, len(LEVELS) - 1))], levels), why, source, handoff


def tmux_type(pane, *items, delay=0.0):
    """Digita no painel do agy num processo separado (o hook já pode ter retornado)."""
    script = ["sleep", str(delay)] if delay else ["true"]
    cmds = [" ".join(script)]
    for kind, val in items:
        if kind == "keys":
            cmds.append(f"tmux send-keys -t {shlex.quote(pane)} -l -- {shlex.quote(val)}")
        elif kind == "altm":   # o agy põe a mensagem na fila enquanto encerra o turno; alt+m envia na hora
            cmds.append(f"tmux send-keys -t {shlex.quote(pane)} M-m")
        elif kind == "enter":
            cmds.append(f"tmux send-keys -t {shlex.quote(pane)} Enter")
        elif kind == "paste":
            cmds.append(f"printf %s {shlex.quote(val)} | tmux load-buffer -b agyturbo - && "
                        f"tmux paste-buffer -p -d -b agyturbo -t {shlex.quote(pane)}")
        elif kind == "sleep":
            cmds.append(f"sleep {float(val)}")
    subprocess.Popen(["sh", "-c", " && ".join(cmds)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


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
        state.pop("resubmit", None)          # é a mensagem que nós mesmos reenviamos: já está no nível certo
        common.save("effortless.json", state)
        return {}
    if not c["auto"] or not msg.strip() or msg.lstrip().startswith("/") or not current:
        common.save("effortless.json", state)
        return {}
    t0 = time.time()
    lvl, why, source, handoff = decide(msg, current, levels, ev, c)
    state.update({"decided": lvl, "reason": why, "source": source, "handoff": handoff,
                  "judge_ms": int((time.time() - t0) * 1000), "t": time.time(), "pending": None})
    pane = os.environ.get("TMUX_PANE") if os.environ.get("TMUX") else None
    out = {}
    if lvl != current:
        if not pane:
            state["suggest"] = lvl
        elif LEVELS.index(lvl) > LEVELS.index(current) and c["resubmit"]:
            # subir vale já: troca o esforço e reenvia a mensagem; esta chamada é encerrada
            state["resubmit"] = {"hash": h, "t": time.time(), "to": lvl}
            items = [("keys", f"/effort {lvl}"), ("enter", None), ("sleep", "0.4")]
            items += [("paste", msg)] if "\n" in msg else [("keys", msg)]
            items += [("sleep", "0.2"), ("enter", None), ("sleep", "0.6"), ("altm", None)]
            tmux_type(pane, *items, delay=0.5)
            out = {"terminationBehavior": "terminate"}
        elif LEVELS.index(lvl) > LEVELS.index(current):
            tmux_type(pane, ("keys", f"/effort {lvl}"), ("enter", None))
        else:
            state["pending"] = lvl            # descer só no fim do turno
        if pane:
            state.pop("suggest", None)
    else:
        state.pop("suggest", None)
    common.save("effortless.json", state)
    return out


def stop(ev):
    state = common.load("effortless.json")
    lvl = state.get("pending")
    pane = os.environ.get("TMUX_PANE") if os.environ.get("TMUX") else None
    if lvl and pane and ev.get("terminationReason") != "TERMINAL_CUSTOM_HOOK":
        tmux_type(pane, ("keys", f"/effort {lvl}"), ("enter", None), delay=0.3)
        state["pending"] = None
        state["current"] = lvl
        common.save("effortless.json", state)
    return {}


def main():
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
        print(json.dumps(main()))
    except Exception:
        print("{}")
