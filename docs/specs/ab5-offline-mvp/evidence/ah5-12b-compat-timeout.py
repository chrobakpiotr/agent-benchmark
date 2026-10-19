import json, os, stat, sys, uuid, shutil, tempfile
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "tests"))
import test_agent_cli_run as t
from agent_benchmark import harness_port, runner
from agent_benchmark.report import load_run, reduce_events
from agent_benchmark.schema import ValidationError
FAKE = t.FAKE_CODEX.replace('''    prompt = sys.stdin.read()''', '''    prompt = sys.stdin.read()
    import time
    open("src/agent_harness/contract.py", "a").write("# edited\\n")
    time.sleep(60)''')
root = ROOT / "runs" / f"scen-{uuid.uuid4().hex[:8]}"; (root / "bin").mkdir(parents=True)
for name, body in (("codex", FAKE), ("claude", t.FAKE_CLAUDE)):
    p = root / "bin" / name; p.write_text(body); p.chmod(p.stat().st_mode | stat.S_IXUSR)
m = json.loads(t.MANIFEST.read_text())
m["task"] = {**m["task"], "path": str((t.MANIFEST.parent / m["task"]["path"]).resolve())}
for c in m["configs"]: c["budget"] = {"max_wall_seconds": 5}
mp = root / "manifest.json"; mp.write_text(json.dumps(m))
env = {k: v for k, v in os.environ.items() if k not in t.BILLING}; env["PATH"] = f"{root / 'bin'}{os.pathsep}{os.environ['PATH']}"
with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(harness_port, "GradingSession", side_effect=ValidationError("x")):
    try: runner.run(mp, root / "run")
    except ValidationError as e: print("stopped:", e)
row = reduce_events(load_run(root / "run")[2])["trials"][0]
res = json.loads(next((root / "run" / "evidence").iterdir()).joinpath("result.json").read_text())
print({k: row[k] for k in ("outcome", "error_code", "drain", "candidate_digest", "grade")}, "exit", res.get("exit_code"),
      sorted(a["name"] for a in res["artifacts"]))
shutil.rmtree(root)
