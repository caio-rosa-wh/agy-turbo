"""Testes do effortless sem modelo nem tmux reais: juiz local, tmux simulado."""
import json, os, sys, tempfile
root = sys.argv[1]
data = tempfile.mkdtemp()
os.environ["AGY_TURBO_DATA"] = data
os.environ.pop("PLUGIN_DATA", None)
sys.path.insert(0, os.path.join(root, "hooks"))
import common, effortless  # noqa: E402
common.DATA = data
common.save("config.json", {"judge": "local"})
common.save("models.json", {"levels": {"gemini-4-hydrogen": ["low", "medium", "high", "xhigh"]}})
typed = []
effortless.tmux_type = lambda pane, *items, delay=0.0: typed.append(items)
c = effortless.cfg()
L = ["low", "medium", "high", "xhigh"]
assert effortless.decide("max effort, revise tudo", "low", L, {}, c)[0] == "xhigh"   # max não existe: o mais próximo
assert effortless.decide("use esforço alto aqui", "low", L, {}, c)[0] == "high"
assert effortless.decide("ok, pode", "high", L, {}, c)[:1] == ("high",)
assert effortless.decide("investigue o deadlock na fila de produção", "low", L, {}, c)[0] == "high"
assert effortless.decide("quantos arquivos tem?", "high", L, {}, c)[0] == "low"
common.save("config.json", {"judge": "local", "economy": True})
assert effortless.decide("refatore a arquitetura", "low", L, {}, effortless.cfg())[0] == "medium"
common.save("config.json", {"judge": "local", "floor": "medium"})
assert effortless.decide("oi", "high", L, {}, effortless.cfg())[0] == "medium"
common.save("config.json", {"judge": "local"})

os.environ["TMUX"], os.environ["TMUX_PANE"] = "/tmp/x", "%7"
ev = {"hookEventName": "PreInvocation", "invocationNum": 0, "modelName": "gemini-4-hydrogen-low",
      "lastUserInput": "investigue a race condition no worker"}
out = effortless.pre_invocation(ev)
assert out == {"terminationBehavior": "terminate"}, out           # subir: reenvia e encerra
flat = [v for items in typed for k, v in items if k == "keys"]
assert flat[0] == "/effort high" and flat[1] == ev["lastUserInput"], flat
assert effortless.pre_invocation(dict(ev, modelName="gemini-4-hydrogen-high")) == {}   # reenvio não é julgado de novo
typed.clear()
out = effortless.pre_invocation(dict(ev, modelName="gemini-4-hydrogen-high", lastUserInput="qual a versão?"))
assert out == {} and not typed and common.load("effortless.json")["pending"] == "low"  # descer espera o fim
effortless.stop({"hookEventName": "Stop", "terminationReason": "NO_TOOL_CALL"})
assert [v for k, v in typed[0] if k == "keys"] == ["/effort low"], typed
assert effortless.pre_invocation(dict(ev, invocationNum=2)) == {}                    # só a 1ª chamada
del os.environ["TMUX"]
typed.clear()
effortless.pre_invocation(dict(ev, lastUserInput="analise a performance do banco", modelName="gemini-4-hydrogen-low"))
assert not typed and common.load("effortless.json")["suggest"] == "high"               # sem tmux: só sugere
os.environ["AGY_TURBO_JUDGE"] = "1"
assert effortless.main() == {}
print("ok")
