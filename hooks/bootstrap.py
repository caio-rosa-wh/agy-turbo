"""Configuração do agy-turbo na máquina, rodada em segundo plano na primeira sessão (e a cada versão nova).

Passos (cada um desliga com a variável indicada = 0):
  1. venv com Textual para o agy-tree                       AGY_TURBO_TREE
  2. comandos agy-tree, agy-turbo, agy-effortless em ~/.local/bin
  3. statusLine do agy apontando para a statusline do turbo  AGY_TURBO_STATUSLINE  (guarda a anterior)
  4. função `agy` no ~/.bashrc / ~/.zshrc (árvore ao lado)   AGY_TURBO_SHELL       (com backup)
  5. lista de modelos e níveis de esforço para o effortless

Tudo é registrado em bootstrap.log e bootstrap.json no PLUGIN_DATA. Desfazer: agy-turbo-uninstall.
"""
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

HOME = os.path.expanduser("~")
VENV = os.environ.get("AGY_TURBO_VENV") or os.path.join(HOME, ".local", "share", "agy-turbo", "venv")
SETTINGS = os.environ.get("AGY_SETTINGS") or os.path.join(HOME, ".gemini", "antigravity-cli", "settings.json")
TEXTUAL = "textual==8.2.8"
MARK_START, MARK_END = "# >>> agy-turbo >>>", "# <<< agy-turbo <<<"
LOG = []


def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    LOG.append(line)
    with open(common.path("bootstrap.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def enabled(var):
    return os.environ.get(var, "1") != "0"


MISSING = []
PKG = [("apt-get", ["apt-get", "install", "-y"], {"tmux": "tmux", "venv": "python3-venv"}),
       ("dnf", ["dnf", "install", "-y"], {"tmux": "tmux", "venv": "python3"}),
       ("pacman", ["pacman", "-S", "--noconfirm", "--needed"], {"tmux": "tmux", "venv": "python"}),
       ("zypper", ["zypper", "install", "-y"], {"tmux": "tmux", "venv": "python3"}),
       ("brew", ["brew", "install"], {"tmux": "tmux", "venv": "python"})]


def venv_possible():
    return os.path.exists(os.path.join(VENV, "bin", "python")) or subprocess.run(
        [sys.executable, "-c", "import ensurepip, venv"], capture_output=True).returncode == 0


def step_deps():
    """tmux e venv do Python: instala sozinho só se o sudo não pedir senha; senão o `agy` pergunta no terminal."""
    need = [n for n, ok in (("tmux", shutil.which("tmux")), ("venv", venv_possible())) if not ok]
    if not need:
        return log("dependências: tmux e venv ok")
    for pm, cmd, names in PKG:
        if not shutil.which(pm):
            continue
        pkgs = [names[n] for n in need]
        prefix = [] if pm == "brew" or os.geteuid() == 0 else ["sudo", "-n"]
        if prefix and subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode != 0:
            break
        if pm == "apt-get":
            subprocess.run(prefix + ["apt-get", "update", "-qq"], capture_output=True, timeout=300)
        r = subprocess.run(prefix + cmd + pkgs, capture_output=True, text=True, timeout=900)
        log(f"dependências: {' '.join(prefix + cmd + pkgs)} -> {'ok' if r.returncode == 0 else 'falhou'}")
        break
    need = [n for n, ok in (("tmux", shutil.which("tmux")), ("venv", venv_possible())) if not ok]
    MISSING.extend(need)
    if need:
        log(f"dependências: faltam {', '.join(need)}; o comando agy vai oferecer a instalação (agy-turbo-setup)")


def step_venv():
    if not enabled("AGY_TURBO_TREE"):
        return log("venv: desligado (AGY_TURBO_TREE=0)")
    if "venv" in MISSING:
        raise RuntimeError("python3-venv ausente (agy-turbo-setup instala)")
    py = os.path.join(VENV, "bin", "python")
    if not os.path.exists(py):
        subprocess.run([sys.executable, "-m", "venv", VENV], check=True, capture_output=True, timeout=120)
        log(f"venv criado em {VENV}")
    ok = subprocess.run([py, "-c", "import textual; print(textual.__version__)"], capture_output=True, text=True)
    if ok.returncode != 0 or ok.stdout.strip() != TEXTUAL.split("==")[1]:
        r = subprocess.run([py, "-m", "pip", "install", "-q", "--disable-pip-version-check", TEXTUAL],
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError("pip install textual falhou: " + r.stderr[-400:])
        log(f"{TEXTUAL} instalado")
    else:
        log("textual já instalado")


def step_bin():
    bindir = os.path.join(HOME, ".local", "bin")
    os.makedirs(bindir, exist_ok=True)
    for name in ("agy-tree", "agy-turbo", "agy-effortless", "agy-turbo-setup", "agy-turbo-uninstall"):
        src = os.path.join(common.ROOT, "bin", name)
        if not os.path.exists(src):
            continue
        os.chmod(src, 0o755)
        dst = os.path.join(bindir, name)
        if os.path.islink(dst) or not os.path.exists(dst):
            if os.path.islink(dst):
                os.remove(dst)
            os.symlink(src, dst)
        else:
            log(f"bin: {dst} existe e não é link; não mexi")
    for f in ("statusline/statusline.sh", "statusline/statusline.py", "shell/agy.bash"):
        p = os.path.join(common.ROOT, f)
        if os.path.exists(p):
            os.chmod(p, 0o755)
    log(f"comandos em {bindir}")


def step_statusline():
    if not enabled("AGY_TURBO_STATUSLINE"):
        return log("statusline: desligada (AGY_TURBO_STATUSLINE=0)")
    cmd = os.path.join(common.ROOT, "statusline", "statusline.sh")
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        cfg = {}
    except ValueError:
        return log(f"statusline: {SETTINGS} inválido, não mexi")
    cur = cfg.get("statusLine") or {}
    if cur.get("command") == cmd:
        return log("statusline: já configurada")
    if not os.path.exists(common.path("previous-statusline.json")):
        common.save("previous-statusline.json", {"statusLine": cfg.get("statusLine")})
    if os.path.exists(SETTINGS):
        shutil.copy2(SETTINGS, SETTINGS + time.strftime(".agy-turbo.bak.%Y%m%d-%H%M%S"))
    cfg["statusLine"] = {"type": "command", "command": cmd, "stack_with_default": False}
    tmp = SETTINGS + ".agy-turbo.tmp"
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    if os.path.exists(SETTINGS):
        os.chmod(tmp, os.stat(SETTINGS).st_mode & 0o777)
    os.replace(tmp, SETTINGS)
    log(f"statusline configurada em {SETTINGS} (anterior guardada)")


def step_shell():
    if not enabled("AGY_TURBO_SHELL"):
        return log("shell: desligado (AGY_TURBO_SHELL=0)")
    src = os.path.join(common.ROOT, "shell", "agy.bash")
    block = f'\n{MARK_START}\n[ -f "{src}" ] && . "{src}"\n{MARK_END}\n'
    for rc in (".bashrc", ".zshrc"):
        p = os.path.join(HOME, rc)
        if not os.path.exists(p) and rc != ".bashrc":
            continue
        text = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
        if MARK_START in text:
            if src in text:
                continue
            # bloco de uma instalação anterior apontando para outro lugar: troca pelo atual
            a, b = text.index(MARK_START), text.find(MARK_END, text.index(MARK_START))
            if b < 0:
                continue
            shutil.copy2(p, p + time.strftime(".agy-turbo.bak.%Y%m%d-%H%M%S"))
            text = text[:a].rstrip("\n") + block + text[b + len(MARK_END):].lstrip("\n")
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            log(f"shell: bloco agy-turbo atualizado em ~/{rc}")
            continue
        if text:
            shutil.copy2(p, p + time.strftime(".agy-turbo.bak.%Y%m%d-%H%M%S"))
        with open(p, "a", encoding="utf-8") as f:
            f.write(block)
        log(f"shell: função agy adicionada em ~/{rc}")


def step_models():
    agy = shutil.which("agy")
    if not agy:
        return log("models: agy fora do PATH")
    r = subprocess.run([agy, "models"], capture_output=True, text=True, timeout=60,
                       env=dict(os.environ, AGY_TURBO_JUDGE="1"))
    levels = {}
    for line in r.stdout.splitlines():
        mid = line.split("\t")[0].strip()
        base, _, lvl = mid.rpartition("-")
        if lvl in common.LEVELS and base:
            levels.setdefault(base, []).append(lvl)
    for base in levels:
        levels[base].sort(key=common.LEVELS.index)
    if levels:
        common.save("models.json", {"t": time.time(), "levels": levels})
        log(f"models: {len(levels)} modelos com níveis de esforço")


def main():
    st = common.load("bootstrap.json")
    st.update({"running_since": time.time(), "version": common.version(), "ok": False})
    common.save("bootstrap.json", st)
    errors = []
    for step in (step_deps, step_venv, step_bin, step_statusline, step_shell, step_models):
        try:
            step()
        except Exception as exc:  # um passo com erro não impede os outros
            errors.append(f"{step.__name__}: {exc}")
            log(f"ERRO {step.__name__}: {exc}")
    st.update({"running_since": 0, "ok": not errors, "errors": errors, "missing": MISSING, "t": time.time()})
    common.save("bootstrap.json", st)
    if MISSING:
        msg = (f"agy-turbo: falta {' e '.join(MISSING)}. Abra um terminal novo e rode agy: ele oferece instalar")
    elif errors:
        msg = "agy-turbo: configuração com erros, veja " + common.path("bootstrap.log")
    else:
        msg = "agy-turbo pronto: abra um terminal novo e rode agy (árvore ao lado)"
    common.save("notice.json", {"t": time.time(), "text": msg})


if __name__ == "__main__":
    main()
