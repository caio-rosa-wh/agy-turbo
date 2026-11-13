#!/usr/bin/env python3
"""Statusline do agy-turbo para o Antigravity CLI. Só biblioteca padrão (sem jq).

Linha 1: modelo | esforço   tok usado/total (pct) barra   custo
Linha 2: usage   5h barra pct   7d barra pct          (layout do Cockpit do Claude Code)
Linha 3: effortless: ✦ esforço · cache · contexto   régua de níveis   auto: motivo · próximos passos

Variáveis: COCKPIT_BAR (largura), COCKPIT_QUOTA=auto|gemini|3p, COCKPIT_RESET=1, COCKPIT_STATE=1,
COCKPIT_ASCII=1, COCKPIT_NO_EFFORTLESS=1, AGY_CACHE_TTL_MIN, NO_COLOR=1.
"""
import calendar
import json
import os
import re
import sys
import time

E = os.environ
DATA = E.get("AGY_TURBO_DATA") or os.path.expanduser("~/.gemini/antigravity-cli/plugin_data/agy-turbo")
COLOR = not E.get("NO_COLOR")
R = "\033[0m" if COLOR else ""
PILL, CTX, FIVE, WEEK = "1;38;2;255;255;255;48;2;43;47;58", "38;2;143;184;218", "38;2;156;192;159", "38;2;216;184;112"
WARN, DIM, ACC = "38;2;232;125;110", "2", "38;2;187;154;247"
FULL, EMPTY = ("#", ".") if E.get("COCKPIT_ASCII") else ("￭", "･")


def c(code: str) -> str:
    return f"\033[{code}m" if COLOR and code else ""


def num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def compact(n) -> str:
    n = num(n) or 0
    if n < 1000:
        return str(int(n))
    v, s = (n / 1000, "k") if n < 1_000_000 else (n / 1_000_000, "M")
    t = f"{v:.1f}"
    return (t[:-2] if t.endswith(".0") else t) + s


def dur(s) -> str:
    s = int(s)
    if s >= 86400:
        return f"{s // 86400}d{(s % 86400) // 3600}h"
    if s >= 3600:
        return f"{s // 3600}h{(s % 3600) // 60:02d}m"
    return f"{(s + 59) // 60}m"


def bar(p, w) -> str:
    p = max(0, min(100, int(p or 0)))
    f = (p * w + 50) // 100
    return FULL * f + EMPTY * (w - f)


def hot(p, col) -> str:
    return WARN if (p or 0) >= 80 else col


def load(name):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def last_call(transcript):
    """(epoch, cache_read_tokens) da última chamada ao modelo no transcript."""
    try:
        with open(transcript, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 60_000))
            lines = f.read().decode("utf-8", errors="replace").splitlines()
    except (OSError, TypeError):
        return None
    for line in reversed(lines):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "PLANNER_RESPONSE" and d.get("created_at"):
            try:
                t = calendar.timegm(time.strptime(d["created_at"][:19], "%Y-%m-%dT%H:%M:%S"))
            except ValueError:
                return None
            return t, int(d.get("cache_read_tokens") or 0)
    return None


def main() -> str:
    raw = sys.stdin.read()
    try:
        d = json.loads(raw)
        if not isinstance(d, dict):
            raise ValueError
    except ValueError:
        return "agy-cockpit: JSON inválido\n"
    if os.path.isdir(DATA):   # o effortless lê o % de contexto daqui
        try:
            tmp = os.path.join(DATA, ".statusline.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(raw)
            os.replace(tmp, os.path.join(DATA, "statusline.json"))
        except OSError:
            pass

    m = d.get("model") or {}
    name = m.get("display_name") or m.get("id") or "?"
    model = re.sub(r"\s*\([^)]*\)\s*$", "", name)
    effort = m.get("effort") or ""
    cw = d.get("context_window") or {}
    used, total = num(cw.get("total_input_tokens")) or 0, num(cw.get("context_window_size")) or 0
    pct = round(num(cw.get("used_percentage")) or 0)
    cost = d.get("cost")
    if isinstance(cost, dict):
        cost = cost.get("total_cost_usd", cost.get("estimated_cost_usd"))
    cost = num(cost)
    state = d.get("agent_state") or ""

    pref = E.get("COCKPIT_QUOTA", "auto")
    grp = pref if pref != "auto" else (
        "3p" if re.search(r"claude|gpt|sonnet|opus|haiku", f"{name} {m.get('id', '')}", re.I) else "gemini")
    q = d.get("quota") or {}

    def bucket(suffix):
        b = q.get(f"{grp}-{suffix}") or next((v for k, v in q.items() if k.endswith(f"-{suffix}")), None) or {}
        rf = num(b.get("remaining_fraction"))
        return (None if rf is None else round((1 - rf) * 100)), num(b.get("reset_in_seconds"))

    q5, r5 = bucket("5h")
    qw, rw = bucket("weekly")

    cols = int(num(d.get("terminal_width")) or 0) or int(num(E.get("COLUMNS")) or 100)
    if E.get("COCKPIT_BAR"):
        w = int(E["COCKPIT_BAR"])
    else:
        w = max(6, min(30, (cols - 46) // 2))

    # linha 1
    l1 = f"{c(PILL)} {model} {R}"
    if effort:
        l1 += f" {c(DIM)}|{R} {effort}"
    if E.get("COCKPIT_STATE") and state and state != "idle":
        l1 += f" {c(DIM)}· {state}{R}"
    l1 += f"  {c(DIM + ';' + CTX)}tok {R}{c('1;' + CTX)}{compact(used)}/{compact(total)} ({pct}%){R} "
    l1 += f"{c(WARN)}{bar(pct, w)}{R}" if pct >= 80 else bar(pct, w)
    if cost is not None:
        l1 += f"  ${cost:.2f}"

    # linha 2
    def seg(label, p, r, col):
        s = f"{c(DIM + ';' + col)}{label} {R}"
        if p is None:
            return s + f"{c(DIM)}{bar(0, w)}  --{R}"
        s += f"{c(col)}{bar(p, w)}{R} {c('1;' + hot(p, col))}{p:3d}%{R}"
        if E.get("COCKPIT_RESET") and r:
            s += f" {c(DIM)}↻{dur(r)}{R}"
        return s
    l2 = f" usage  {seg('5h', q5, r5, FIVE)}  {seg('7d', qw, rw, WEEK)}"
    out = [l1, l2]

    # linha 3: effortless
    if not E.get("COCKPIT_NO_EFFORTLESS"):
        st, cf, nt = load("effortless.json"), load("config.json"), load("notice.json")
        lvl = effort or st.get("current") or "?"
        s3 = f"{c(ACC)}✦{R} {c('1')}{lvl}{R}"
        lc = last_call(d.get("transcript_path"))
        if lc:
            ttl = num(E.get("AGY_CACHE_TTL_MIN")) or (60 if re.search("claude", name, re.I) else 5)
            left = ttl * 60 - (time.time() - lc[0])
            if left > 0:
                s3 += f" {c(DIM)}·{R} cache ~{int((left + 59) // 60)}m" + (f" ({compact(lc[1])})" if lc[1] else "")
            else:
                s3 += f" {c(DIM)}· cache frio{R}"
        s3 += f" {c(DIM)}·{R} {pct}% context"
        gauge = ""
        for l in st.get("levels") or ["low", "medium", "high"]:
            gauge += f" {c('1;' + ACC)}[ {l} ]{R}" if l == lvl else f" {c(DIM)}{l}{R}"
        if cf.get("auto", True):
            tail = f"{c(ACC)}auto{R}"
            if st.get("reason"):
                tail += f"{c(DIM)}: {str(st['reason'])[:50]}{R}"
            if st.get("pending"):
                tail += f" {c(DIM)}· depois desta resposta → {st['pending']}{R}"
            if st.get("suggest"):
                tail += f" {c(WARN)}· sugestão: /effort {st['suggest']}{R}"
        else:
            tail = f"{c(DIM)}esforço manual (agy-effortless on){R}"
        hint = {"compacting": "compactando…", "compact": "contexto cheio: /compact",
                "handoff": "assunto novo: /handoff"}.get(st.get("hint") or "")
        if hint:
            tail += f" {c(WARN)}· {hint}{R}"
        out.append(f" {s3}  {gauge}   {tail}")
        if (num(nt.get("t")) or 0) > time.time() - 600 and nt.get("text"):
            out.append(f" {c('1;' + ACC)}{nt['text']}{R}")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    try:
        sys.stdout.write(main())
    except Exception as exc:  # a statusline nunca pode quebrar a tela do agy
        sys.stdout.write(f"agy-turbo statusline: {exc}\n")
