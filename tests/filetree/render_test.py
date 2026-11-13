"""Teste headless do agy-tree: árvore carrega, git status aparece, evento de escrita abre a pasta e brilha."""
import asyncio, json, os, subprocess, sys, tempfile, time
sys.path.insert(0, sys.argv[1])
import agy_tree

async def main():
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, "src/deep"))
    open(os.path.join(root, "src/deep/a.py"), "w").write("x = 1\n")
    open(os.path.join(root, "README.md"), "w").write("# t\n")
    subprocess.run(["git", "-C", root, "init", "-q"], check=True)
    act = os.path.join(root, ".act.jsonl"); open(act, "w").close()
    app = agy_tree.AgyTree(agy_tree.Path(root), act)
    async with app.run_test(size=(70, 20)) as pilot:
        await pilot.pause(1.0)
        lines = lambda: "\n".join(app.tree.render_line(y).text for y in range(app.tree.size.height))
        assert "README.md ?" in lines(), lines()
        assert "a.py" not in lines()
        with open(act, "a") as f:
            f.write(json.dumps({"t": time.time(), "kind": "write", "paths": [os.path.join(root, "src/deep/a.py")], "cwd": root}) + "\n")
            f.write(json.dumps({"t": time.time(), "kind": "cmd", "paths": [], "cmd": "pytest -q", "cwd": root}) + "\n")
        await pilot.pause(0.8)
        assert "a.py" in lines(), "seguir o agente devia abrir src/deep"
        assert "a.py" in str(app.activity) or any(k.endswith("a.py") for k in app.activity)
        assert "pytest -q" in app.last_cmd
        await pilot.press("p"); await pilot.pause(0.3)
        await pilot.press("s"); await pilot.press(*"a.p"); await pilot.pause(0.3)
        assert app.query_one("#results").option_count >= 1
    print("ok")

asyncio.run(main())
