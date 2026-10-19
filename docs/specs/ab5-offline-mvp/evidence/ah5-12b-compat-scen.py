"""AH5-12b compatibility scenarios: fake codex per scenario, the benchmark runner, then how each trial is classified."""
import json, os, stat, sys, uuid, shutil
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "tests"))
import test_agent_cli_run as t
from agent_benchmark import harness_port, runner
from agent_benchmark.report import load_run, reduce_events
from agent_benchmark.schema import ValidationError

FAKE = t.FAKE_CODEX.replace('''if args and args[0] == "exec":
    prompt = sys.stdin.read()''', '''if args and args[0] == "exec":
    prompt = sys.stdin.read()
    scen = os.environ.get("SCEN")
    turn = json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "cached_input_tokens": 0,
                                                           "cache_write_input_tokens": 0, "output_tokens": 1}})
    if scen == "empty_patch":
        print(turn); sys.exit(0)
    if scen in ("nonzero_exit", "nonzero_withheld"):
        open("src/agent_harness/contract.py", "a").write("# edited\\n")
        if scen == "nonzero_withheld":
            print("sk-" + "A" * 40)
        print(turn); sys.exit(3)
    if scen == "exit0_withheld_size":
        open("src/agent_harness/contract.py", "a").write("# edited\\n")
        sys.stdout.write("x" * (9 << 20) + "\\n"); print(turn); sys.exit(0)
    if scen == "exit0_withheld_credential":
        open("src/agent_harness/contract.py", "a").write("# edited sk-" + "B" * 40 + "\\n")
        print(turn); sys.exit(0)
    if scen == "stderr_withheld":
        open("src/agent_harness/contract.py", "a").write("# edited\\n")
        sys.stderr.write("token sk-" + "C" * 40 + "\\n"); print(turn); sys.exit(0)''')
results = {}
for scen in ("exit0_withheld_size", "exit0_withheld_credential", "nonzero_exit", "nonzero_withheld", "empty_patch",
             "stderr_withheld"):
    root = ROOT / "runs" / f"scen-{uuid.uuid4().hex[:8]}"
    (root / "bin").mkdir(parents=True)
    for name, body in (("codex", FAKE), ("claude", t.FAKE_CLAUDE)):
        p = root / "bin" / name; p.write_text(body); p.chmod(p.stat().st_mode | stat.S_IXUSR)
    env = {k: v for k, v in os.environ.items() if k not in t.BILLING}
    env.update(PATH=f"{root / 'bin'}{os.pathsep}{os.environ['PATH']}", SCEN=scen)
    with mock.patch.dict(os.environ, env, clear=True), \
         mock.patch.object(harness_port, "GradingSession", side_effect=ValidationError("no grading target in this check")):
        runner._SESSIONS.clear()
        try:
            out = runner.run(t.MANIFEST, root / "run"); stop = None
        except ValidationError as e:
            out, stop = root / "run", str(e)[:90]
    row = reduce_events(load_run(out)[2])["trials"][0]
    ev = next((out / "evidence").iterdir())
    res = json.loads((ev / "result.json").read_text())
    grade = [json.loads(l) for l in (out / "events.jsonl").read_text().splitlines() if '"type": "grade"' in l]
    results[scen] = {"outcome": row["outcome"], "exit_code": res.get("exit_code"), "error_code": row["error_code"],
                     "candidate": bool(row["candidate_digest"]),
                     "artifacts": sorted(a["name"] for a in res["artifacts"]),
                     "benchmark_grade": row["grade"],
                     "grade_detail": grade[0]["criteria"][0] if grade else None, "run_stopped": stop}
    shutil.rmtree(root)
print(json.dumps(results, indent=1))
