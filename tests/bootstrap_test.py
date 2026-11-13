"""Bootstrap num HOME vazio: comandos, statusline (guardando a anterior), shell; idempotente. Sem venv nem rede."""
import json, os, subprocess, sys, tempfile
root = sys.argv[1]
home = tempfile.mkdtemp()
env = dict(os.environ, HOME=home, AGY_TURBO_DATA=os.path.join(home, "data"), PLUGIN_ROOT=root,
           AGY_TURBO_TREE="0", AGY_SETTINGS=os.path.join(home, "settings.json"), PATH="/usr/bin:/bin")
env.pop("PLUGIN_DATA", None)
json.dump({"statusLine": {"type": "command", "command": "/antiga.sh"}, "x": 1}, open(env["AGY_SETTINGS"], "w"))
for _ in range(2):
    subprocess.run([sys.executable, "-I", os.path.join(root, "hooks", "bootstrap.py")], env=env, check=True)
cfg = json.load(open(env["AGY_SETTINGS"]))
assert cfg["statusLine"]["command"] == os.path.join(root, "statusline", "statusline.sh") and cfg["x"] == 1
prev = json.load(open(os.path.join(home, "data", "previous-statusline.json")))
assert prev["statusLine"]["command"] == "/antiga.sh"
rc = open(os.path.join(home, ".bashrc")).read()
assert rc.count("# >>> agy-turbo >>>") == 1 and os.path.join(root, "shell", "agy.bash") in rc
assert os.path.islink(os.path.join(home, ".local", "bin", "agy-tree"))
st = json.load(open(os.path.join(home, "data", "bootstrap.json")))
assert st["version"] and st["running_since"] == 0
print("ok")
