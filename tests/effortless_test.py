"""Testes do effortless sem modelo nem tmux reais: regras locais, juiz simulado, tmux simulado."""
import io, json, os, sys, tempfile
root = sys.argv[1]
data = tempfile.mkdtemp()
os.environ["AGY_TURBO_DATA"] = data
os.environ.pop("PLUGIN_DATA", None)
sys.path.insert(0, os.path.join(root, "hooks"))
import common, effortless as e  # noqa: E402
common.DATA = data
common.save("config.json", {"judge": "local"})
common.save("models.json", {"levels": {"gemini-4-hydrogen": ["low", "medium", "high", "xhigh"]}})
typed = []
e.tmux_type = lambda pane, *items, delay=0.0: typed.append([v for k, v in items if k == "keys"])
spawned = []
e.subprocess.Popen = lambda *a, **k: spawned.append(a)
L = ["low", "medium", "high", "xhigh"]
c = e.cfg()
# regras locais
assert e.local("max effort, revise tudo", "low", L, c)[0::2] == ("xhigh", True)
assert e.local("ok, pode", "high", L, c)[0] == "high"
assert e.local("investigue o deadlock na fila", "low", L, c) == ("high", "tarefa pesada", True, True)
assert e.local("investigue o deadlock na fila", "medium", L, c)[2] is False
assert e.local("quantos arquivos tem?", "high", L, c)[0] == "low"
assert e.local("quantos arquivos tem?", "high", L, c)[3] is True          # regra clara: auto não chama o juiz
assert e.local("ajuste a função de parse para aceitar datas no formato brasileiro", "low", L, c)[3] is False
assert e.limits("high", L, dict(c, economy=True)) == "medium"
assert e.limits("low", L, dict(c, floor="medium")) == "medium"
# parser com a saída real do agy -p (dois objetos JSON e structured_output)
real = ('{"status":"SUCCESS","response":"{\\"effort\\": \\"low\\"}\\n{\\"confidence\\":1,\\"effort\\":\\"low\\",'
        '\\"reason\\":\\"x\\"}\\n","structured_output":{"effort":"high","confidence":0.8,"reason":"r"}}')
assert e.parse_verdict(real, L)[:2] == ("high", 0.8)
assert e.parse_verdict('{"response":"bla {\\"effort\\":\\"medium\\",\\"confidence\\":0.9}"}', L)[0] == "medium"
assert e.parse_verdict("lixo", L) is None

os.environ["TMUX"], os.environ["TMUX_PANE"] = "/tmp/x", "%7"
ev = {"hookEventName": "PreInvocation", "invocationNum": 0, "modelName": "gemini-4-hydrogen-low",
      "lastUserInput": "investigue a race condition no worker"}
assert e.pre_invocation(ev) == {"terminationBehavior": "terminate"}         # sinal forte: reenvia já
assert typed[-1] == ["/effort high", ev["lastUserInput"]], typed
assert e.pre_invocation(dict(ev, modelName="gemini-4-hydrogen-high")) == {}    # o reenvio não é julgado de novo
# modo auto: pedido simples não chama o juiz
common.save("config.json", {"judge": "auto"})
spawned.clear()
e.pre_invocation(dict(ev, modelName="gemini-4-hydrogen-high", lastUserInput="qual a versão?"))
assert not spawned, "regra clara não deve chamar o juiz"
# juiz em segundo plano: mensagem comum em medium, juiz pede high com o turno rodando -> sobe no meio
common.save("config.json", {"judge": "auto"})
common.save("judge-run.json", {"t": 0})
typed.clear(); spawned.clear()
m = "ajuste a função de parse para aceitar datas no formato brasileiro"
out = e.pre_invocation(dict(ev, modelName="gemini-4-hydrogen-medium", lastUserInput=m))
assert out == {} and spawned, "deve disparar o juiz sem bloquear"
spawned.clear()
e.pre_invocation(dict(ev, modelName="gemini-4-hydrogen-medium", lastUserInput=m + " por favor"))
assert not spawned, "dois juízes em menos de judge_gap: o segundo não roda"
common.save("effortless.json", dict(common.load("effortless.json"), turn=__import__("hashlib").sha1(m.encode()).hexdigest()))
e.judge = lambda *a, **k: ("high", 0.9, "parsing com casos de borda", False)
e.run_judge()
assert typed[-1] == ["/effort high"] and common.load("effortless.json")["raised_mid_turn"]
# juiz pede menos -> fica para o fim do turno
typed.clear()
common.save("judge-run.json", {"t": 0}); common.save("config.json", {"judge": "flash"})   # força o juiz
e.pre_invocation(dict(ev, modelName="gemini-4-hydrogen-high", lastUserInput="mostra o diff que você fez agora"))
e.judge = lambda *a, **k: ("low", 0.9, "só mostrar", True)
common.save("statusline.json", {"context_window": {"used_percentage": 85}})
e.run_judge()
st = common.load("effortless.json")
assert st["pending"] == "low" and st["hint"] == "handoff" and not typed
e.stop({"hookEventName": "Stop", "terminationReason": "NO_TOOL_CALL"})                 # fim: desce e compacta
assert typed[-1] == ["/effort low", "/compact"], typed
typed.clear()
e.stop({"hookEventName": "Stop", "terminationReason": "NO_TOOL_CALL"})
assert not typed, "não compacta de novo em seguida"
assert e.pre_invocation(dict(ev, invocationNum=2)) == {}
# sem tmux: só sugere
del os.environ["TMUX"]
common.save("config.json", {"judge": "local"})
typed.clear()
e.pre_invocation(dict(ev, lastUserInput="analise a performance do banco", modelName="gemini-4-hydrogen-low"))
assert not typed and common.load("effortless.json")["suggest"] == "high"
os.environ["AGY_TURBO_JUDGE"] = "1"
sys.stdin = io.StringIO("{}")
assert e.main() == {}
print("ok")
