#!/usr/bin/env python3
"""Desenha gráficos em Unicode para colar numa resposta do agy (bloco ```text).

Exemplos:
  chart.py bar   --title "ALB 5xx" --labels 12:09,12:24,12:39 --values 2,4,82
  chart.py hbar  --labels api,web,db --values 120,45,300 --unit ms
  chart.py line  --labels jan,fev,mar,abr --series "east:3,5,4,8" --series "west:1,2,6,5"
  chart.py func  --expr "cos(x)" --from 0 --to 2*pi --title "f(x) = cos(x)"
  chart.py spark --values 1,5,2,8,3

Só biblioteca padrão. Saída sem cor (o agy mostra blocos de código como texto puro).
"""
import argparse
import ast
import math
import sys

BLOCKS = " ▁▂▃▄▅▆▇█"
HBLOCKS = " ▏▎▍▌▋▊▉█"
MARKERS = "●○■□▲△◆◇"


def nums(s):
    return [float(v) for v in s.replace(";", ",").split(",") if v.strip() != ""]


def fmt(v):
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    if abs(v) >= 100:
        return f"{v:.0f}"
    return f"{v:.2f}".rstrip("0").rstrip(".")


def nice_ticks(lo, hi, n=5):
    if hi == lo:
        hi = lo + 1
    raw = (hi - lo) / max(n - 1, 1)
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=raw)
    start = math.floor(lo / step) * step
    ticks, t = [], start
    while t <= hi + step * 1e-9:
        ticks.append(round(t, 10))
        t += step
    if ticks[-1] < hi:
        ticks.append(round(t, 10))
    return ticks


def title_line(title, width):
    title = title.strip()
    return [title.center(width).rstrip(), ""] if title else []


def bar(labels, values, height, title, unit):
    n = len(values)
    ticks = nice_ticks(min(0.0, min(values)), max(0.0, max(values)))
    lo, hi = ticks[0], ticks[-1]
    span = hi - lo or 1
    colw = max(3, max(len(l) for l in labels) if labels else 3, max(len(fmt(v)) for v in values))
    barw = max(1, colw - 1)
    ylab = max(len(fmt(t)) for t in ticks)
    rows = height * 8                       # resolução em oitavos de célula
    base = round((0 - lo) / span * rows)    # linha do zero
    tops = [round((v - lo) / span * rows) for v in values]
    tick_rows = {round((t - lo) / span * (height - 1)): t for t in ticks}
    # rótulo do valor: acima da barra (positivos) ou abaixo (negativos)
    label_row = []
    for v, t in zip(values, tops):
        label_row.append(min(height - 1, (t + 7) // 8) if v >= 0 else max(0, t // 8 - 1))
    out = title_line((title + (f" ({unit})" if unit else "")) if title else "", ylab + 2 + n * (colw + 1))
    for r in range(height - 1, -1, -1):
        t = tick_rows.get(r)
        line = (fmt(t).rjust(ylab) + " ┤") if t is not None else (" " * ylab + " │")
        cell_lo, cell_hi = r * 8, r * 8 + 8
        for i, (v, top) in enumerate(zip(values, tops)):
            a_, b_ = (base, top) if v >= 0 else (top, base)
            fill = max(0, min(cell_hi, b_) - max(cell_lo, a_))
            if fill >= 8:
                g = "█" * barw
            elif fill > 0 and v >= 0 and b_ < cell_hi:
                g = BLOCKS[fill] * barw          # topo fracionário
            elif fill > 0:
                g = "█" * barw if fill >= 4 else " " * barw
            elif label_row[i] == r:
                g = fmt(v).center(barw)[:max(barw, len(fmt(v)))]
            else:
                g = " " * barw
            line += " " + g.ljust(colw)
        out.append(line.rstrip())
    out.append(" " * ylab + " └" + "─" * (n * (colw + 1)))
    out.append(" " * (ylab + 2) + "".join(" " + l[:colw].center(barw).ljust(colw) for l in labels).rstrip())
    return out


def hbar(labels, values, width, title, unit):
    vmax = max(values) or 1
    lw = max(len(l) for l in labels)
    out = title_line((title + (f" ({unit})" if unit else "")) if title else "", lw + width + 10)
    for l, v in zip(labels, values):
        cells = max(0.0, v) / vmax * width
        full = int(cells)
        frac = int(round((cells - full) * 8))
        b = "█" * full + (HBLOCKS[frac] if frac and full < width else "")
        out.append(f"{l.rjust(lw)} │{b} {fmt(v)}{unit and ' ' + unit}".rstrip())
    return out


def spark(values):
    lo, hi = min(values), max(values)
    span = hi - lo or 1
    return ["".join(BLOCKS[1 + round((v - lo) / span * 7)] for v in values)]


class Canvas:
    """Grade de pontos braille (2x4 por célula)."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.cells = [[0] * w for _ in range(h)]
        self.marks = {}

    def dot(self, px, py):
        cx, cy = px // 2, py // 4
        if 0 <= cx < self.w and 0 <= cy < self.h:
            bit = {(0, 0): 0, (0, 1): 1, (0, 2): 2, (1, 0): 3, (1, 1): 4, (1, 2): 5, (0, 3): 6, (1, 3): 7}[(px % 2, py % 4)]
            self.cells[cy][cx] |= 1 << bit

    def segment(self, x0, y0, x1, y1):
        steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for s in range(steps + 1):
            t = s / steps
            self.dot(round(x0 + (x1 - x0) * t), round(y0 + (y1 - y0) * t))

    def mark(self, cx, cy, ch):
        if 0 <= cx < self.w and 0 <= cy < self.h:
            self.marks[(cx, cy)] = ch

    def rows(self):
        for y in range(self.h):
            yield "".join(self.marks.get((x, y)) or (chr(0x2800 + self.cells[y][x]) if self.cells[y][x] else " ") for x in range(self.w))


def line(labels, series, width, height, title, xs=None, xlabels_at=None):
    allv = [v for _, vs in series for v in vs]
    ticks = nice_ticks(min(allv), max(allv))
    lo, hi = ticks[0], ticks[-1]
    span = hi - lo or 1
    ylab = max(len(fmt(t)) for t in ticks)
    cv = Canvas(width, height)
    pw, ph = width * 2 - 1, height * 4 - 1
    multi = len(series) > 1
    for si, (_, vs) in enumerate(series):
        n = len(vs)
        pts = []
        for i, v in enumerate(vs):
            fx = (xs[i] - xs[0]) / ((xs[-1] - xs[0]) or 1) if xs else (i / (n - 1) if n > 1 else 0)
            pts.append((fx * pw, ph - (v - lo) / span * ph))
        for (a, b), (c, d) in zip(pts, pts[1:]):
            cv.segment(a, b, c, d)
        if multi or n <= 24:
            for x, y in pts if (multi or n <= 24) and not xs else []:
                cv.mark(round(x) // 2, round(y) // 4, MARKERS[si % len(MARKERS)] if multi else "●")
    # zero line
    zero_row = None
    if lo < 0 < hi:
        zero_row = round(ph - (0 - lo) / span * ph) // 4
    tick_rows = {}
    for t in ticks:
        tick_rows.setdefault(round((hi - t) / span * (height - 1)), t)
    out = title_line(title, ylab + 2 + width)
    for r, txt in enumerate(cv.rows()):
        if r == zero_row:
            txt = "".join("┄" if ch == " " else ch for ch in txt)
        t = tick_rows.get(r)
        out.append(((fmt(t).rjust(ylab) + " ┤") if t is not None else (" " * ylab + " │")) + txt.rstrip())
    out.append(" " * ylab + " └" + "─" * width)
    # rótulos do eixo x espalhados sem sobrepor
    axis = [" "] * (width + 20)
    pos_labels = xlabels_at or [(i / (len(labels) - 1) if len(labels) > 1 else 0, l) for i, l in enumerate(labels)]
    last_end = -2
    for fx, l in pos_labels:
        c = round(fx * (width - 1))
        start = max(0, min(c - len(l) // 2, width - len(l)))
        if start <= last_end + 1:
            continue
        axis[start:start + len(l)] = list(l)
        last_end = start + len(l) - 1
    out.append(" " * (ylab + 2) + "".join(axis).rstrip())
    if multi:
        out.append("")
        out.append(" " * (ylab + 2) + "   ".join(f"{MARKERS[i % len(MARKERS)]} {name}" for i, (name, _) in enumerate(series)))
    return out


SAFE = {k: getattr(math, k) for k in ("sin", "cos", "tan", "exp", "log", "log10", "sqrt", "pi", "e", "atan", "asin", "acos", "sinh", "cosh", "tanh", "floor", "ceil")}
SAFE["abs"] = abs
_OPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: a ** b, ast.Mod: lambda a, b: a % b}


def evaluate(expr, x):
    """Avalia expressão aritmética de x sem eval: só números, x, + - * / ** % e funções de math."""
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name):
            if node.id == "x":
                return x
            if node.id in SAFE and not callable(SAFE[node.id]):
                return SAFE[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = ev(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and callable(SAFE.get(node.func.id))
                and not node.keywords):
            return SAFE[node.func.id](*[ev(a) for a in node.args])
        raise ValueError(f"expressão não permitida: {ast.unparse(node)}")
    return ev(ast.parse(expr, mode="eval"))


def pi_label(v):
    k = v / math.pi
    for den in (1, 2, 3, 4, 6):
        num = round(k * den)
        if abs(num / den - k) < 1e-9:
            if num == 0:
                return "0"
            g = math.gcd(num, den)
            num, den = num // g, den // g
            n = "π" if num == 1 else ("-π" if num == -1 else f"{num}π")
            return n if den == 1 else f"{n}/{den}"
    return fmt(v)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["bar", "hbar", "line", "func", "spark"])
    ap.add_argument("--labels", default="")
    ap.add_argument("--values", default="")
    ap.add_argument("--series", action="append", default=[], help='"nome:1,2,3" (repita para várias linhas)')
    ap.add_argument("--expr", help="função de x, ex.: cos(x), x**2, exp(-x)*sin(5*x)")
    ap.add_argument("--from", dest="x0", default="0")
    ap.add_argument("--to", dest="x1", default="2*pi")
    ap.add_argument("--title", default="")
    ap.add_argument("--unit", default="")
    ap.add_argument("--width", type=int, default=60)
    ap.add_argument("--height", type=int, default=12)
    a = ap.parse_args()
    a.width = max(10, min(a.width, 100))
    a.height = max(4, min(a.height, 30))
    labels = [l.strip() for l in a.labels.split(",")] if a.labels else []

    if a.kind == "func":
        if not a.expr:
            ap.error("func precisa de --expr")
        x0, x1 = evaluate(a.x0, 0), evaluate(a.x1, 0)
        n = a.width * 2
        xs = [x0 + (x1 - x0) * i / (n - 1) for i in range(n)]
        ys = [evaluate(a.expr, x) for x in xs]
        # rótulos em múltiplos de π quando o intervalo é em π, senão 5 marcas
        use_pi = "pi" in a.x0 + a.x1
        if use_pi:
            step = math.pi / 2 if (x1 - x0) <= 4 * math.pi else math.pi
            marks, t = [], math.ceil(x0 / step - 1e-9) * step
            while t <= x1 + 1e-9:
                marks.append(((t - x0) / (x1 - x0), pi_label(t)))
                t += step
        else:
            marks = [(i / 4, fmt(x0 + (x1 - x0) * i / 4)) for i in range(5)]
        out = line([], [(a.expr, ys)], a.width, a.height, a.title, xs=xs, xlabels_at=marks)
    else:
        values = nums(a.values) if a.values else []
        if a.kind == "line":
            series = []
            for s in a.series:
                name, _, vs = s.partition(":")
                series.append((name.strip(), nums(vs)))
            if not series and values:
                series = [("", values)]
            if not series:
                ap.error("line precisa de --values ou --series")
            n = len(series[0][1])
            if not labels:
                labels = [str(i + 1) for i in range(n)]
            out = line(labels, series, a.width, a.height, a.title)
        else:
            if not values:
                ap.error(f"{a.kind} precisa de --values")
            if not labels and a.kind != "spark":
                labels = [str(i + 1) for i in range(len(values))]
            if labels and len(labels) != len(values) and a.kind != "spark":
                ap.error("--labels e --values com tamanhos diferentes")
            out = {"bar": lambda: bar(labels, values, a.height, a.title, a.unit),
                   "hbar": lambda: hbar(labels, values, a.width, a.title, a.unit),
                   "spark": lambda: spark(values)}[a.kind]()
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
