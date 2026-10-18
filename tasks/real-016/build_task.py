"""Builds tasks/real-016 hidden cases, expected values and the non-trivial reference patches (run from the repo root).

good.patch is the real diff of agent-harness 91bb3e1 (src/ only). Expected values were taken from the fixed tree. The
rule is in the base's ADR 0002 ("A null unit always means unknown"; unknown is never 0). A `cache: null` step is left
out: reading it as unknown or as a malformed event are both defensible.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

T = Path("tasks/real-016").resolve()


def step(inp, out, cache="full", reasoning=None):
    t = {"input": inp, "output": out}
    if reasoning is not None:
        t["reasoning"] = reasoning
    if cache == "full":
        t["cache"] = {"read": 10, "write": 1}
    elif cache != "absent":
        t["cache"] = cache
    return {"type": "step_finish", "part": {"tokens": t}}


def units(i, o, r, w):
    return {"input_tokens": i, "output_tokens": o, "cache_read_tokens": r, "cache_write_tokens": w}


FAIL = [None, True, None]
CASES = [  # (id, OpenCode events, expected [units, failed, model])
    ("no_cache_single_step", [step(7, 2, "absent")], [units(7, 2, None, None), False, None]),
    ("no_cache_in_one_of_two_steps", [step(100, 20), step(7, 2, "absent")], [units(107, 22, None, None), False, None]),
    ("cache_without_write", [step(100, 20, {"read": 5}), step(50, 4)], [units(150, 24, 15, None), False, None]),
    ("cache_without_read", [step(100, 20, {"write": 3})], [units(100, 20, None, 3), False, None]),
    ("cache_empty_object", [step(100, 20, {})], [units(100, 20, None, None), False, None]),
    ("no_cache_with_reasoning", [step(10, 2, "absent", reasoning=5)], [units(10, 7, None, None), False, None]),
    ("guard_full_cache_sums", [step(100, 20), step(50, 4, {"read": 2, "write": 0}, reasoning=3)],
     [units(150, 27, 12, 1), False, None]),
    ("guard_negative_input_fails", [step(-1, 2)], FAIL),
    ("guard_missing_input_fails",
     [{"type": "step_finish", "part": {"tokens": {"output": 2, "cache": {"read": 0, "write": 0}}}}], FAIL),
    ("guard_float_cache_fails", [step(1, 1, {"read": 1.5, "write": 0})], FAIL),
    ("guard_error_event_marks_failed", [step(100, 20), {"type": "error"}], [units(100, 20, 10, 1), True, None]),
    ("guard_no_steps", [{"type": "text"}], FAIL),
]
OLD = ('                values = (tokens["input"], tokens["output"], tokens.get("reasoning", 0),\n'
       '                          tokens["cache"]["read"], tokens["cache"]["write"])\n')
VARIANTS = {
    # a missing cache count becomes 0: the ADR says unknown is never 0
    "zero_fill": ('                cache = tokens.get("cache") or {}\n'
                  '                values = (tokens["input"], tokens["output"], tokens.get("reasoning", 0),\n'
                  '                          cache.get("read", 0), cache.get("write", 0))\n'),
}
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
       "GIT_AUTHOR_NAME": "x", "GIT_AUTHOR_EMAIL": "x@x", "GIT_COMMITTER_NAME": "x", "GIT_COMMITTER_EMAIL": "x@x"}


def diff(edit):
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d) / "ws"
        shutil.copytree(T / "base", ws, ignore=shutil.ignore_patterns("__pycache__"))
        for argv in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "base"]):
            subprocess.run(["git", *argv], cwd=ws, env=ENV, check=True, capture_output=True)
        edit(ws)
        return subprocess.run(["git", "diff"], cwd=ws, env=ENV, check=True, capture_output=True).stdout


def absent_only(ws):
    """Handles a step without a cache object, but not a cache object missing one count."""
    subprocess.run(["git", "apply", str(T / "reference" / "good.patch")], cwd=ws, env=ENV, check=True)
    p = ws / "src/agent_harness/execution.py"
    s = p.read_text()
    old = '"cache_read_tokens": cache.get("read"), "cache_write_tokens": cache.get("write")}'
    assert s.count(old) == 1
    p.write_text(s.replace(old, '"cache_read_tokens": cache["read"] if cache else None, '
                                '"cache_write_tokens": cache["write"] if cache else None}', 1))


(T / "hidden" / "cases.json").write_text(json.dumps({"module": "bench_fixtures.oc", "cases": [
    {"id": c, "function": "report", "args": [events]} for c, events, _ in CASES]}, indent=1) + "\n")
(T / "expected" / "expected.json").write_text(json.dumps({c: {"value": w} for c, _, w in CASES}, indent=1) + "\n")
for name, new in VARIANTS.items():
    def edit(ws, new=new):
        p = ws / "src/agent_harness/execution.py"
        s = p.read_text()
        assert s.count(OLD) == 1
        p.write_text(s.replace(OLD, new, 1))
    (T / "reference" / f"{name}.patch").write_bytes(diff(edit))
(T / "reference" / "absent_only.patch").write_bytes(diff(absent_only))
(T / "reference" / "noop.patch").write_bytes(b"")
(T / "reference" / "test_deletion.patch").write_bytes(diff(lambda ws: (ws / "tests/test_agent_cli.py").unlink()))
print(len(CASES), "cases;", ", ".join(VARIANTS), "+ absent_only, good, noop, test_deletion")
