"""Builds tasks/real-017 hidden cases, expected values and the non-trivial reference patches (run from the repo root).

good.patch is the real diff of agent-harness e48a7f5 (src/ only; it also changes the Codex sandbox probe, which no
case exercises). Expected values were taken from the fixed tree. The rule for mixed turns is in the base's ADR 0002
(a null unit always means unknown, never 0). Malformed cache-write values and turns without `cached_input_tokens` are
left out: failing or ignoring a malformed count are both defensible, and the base already reads a missing cache read
as 0.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

T = Path("tasks/real-017").resolve()


def turn(i, o, read, write=None):
    usage = {"input_tokens": i, "cached_input_tokens": read, "output_tokens": o}
    if write is not None:
        usage["cache_write_input_tokens"] = write
    return {"type": "turn.completed", "usage": usage}


def units(i, o, r, w):
    return {"input_tokens": i, "output_tokens": o, "cache_read_tokens": r, "cache_write_tokens": w}


CASES = [  # (id, codex events, expected [units, failed, model])
    ("write_reported_one_turn", [turn(500, 40, 300, 25)], [units(500, 40, 300, 25), False, None]),
    ("write_reported_every_turn", [turn(500, 40, 300, 25), turn(700, 60, 650, 5)],
     [units(1200, 100, 950, 30), False, None]),
    ("write_reported_zero", [turn(500, 40, 300, 0)], [units(500, 40, 300, 0), False, None]),
    ("write_with_failed_turn", [turn(500, 40, 300, 7), {"type": "turn.failed"}], [units(500, 40, 300, 7), True, None]),
    ("guard_write_missing_in_second_turn", [turn(500, 40, 300, 25), turn(700, 60, 650)],
     [units(1200, 100, 950, None), False, None]),
    ("guard_write_missing_in_first_turn", [turn(500, 40, 300), turn(700, 60, 650, 5)],
     [units(1200, 100, 950, None), False, None]),
    ("guard_older_cli_no_write", [turn(500, 40, 300)], [units(500, 40, 300, None), False, None]),
    ("guard_negative_input_fails", [turn(-1, 40, 300, 2)], [None, True, None]),
    ("guard_no_turns", [{"type": "thread.started"}], [None, True, None]),
]
OLD = "    return {**totals, \"cache_write_tokens\": None}, failed, None\n"
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


def replace(old, new):
    def edit(ws):
        p = ws / "src/agent_harness/execution.py"
        s = p.read_text()
        assert s.count(old) == 1
        p.write_text(s.replace(old, new, 1))
    return edit


SUM = ("    totals, turns, failed = {\"input_tokens\": 0, \"output_tokens\": 0, \"cache_read_tokens\": 0}, 0, False\n")
VALUES = ("            values = (usage.get(\"input_tokens\"), usage.get(\"output_tokens\"), "
          "usage.get(\"cached_input_tokens\", 0))\n")


def zero_fill(ws):
    """Counts the field, but a turn without it adds 0: the ADR says unknown is never 0."""
    replace(SUM, SUM.replace('"cache_read_tokens": 0}', '"cache_read_tokens": 0, "cache_write_tokens": 0}'))(ws)
    replace(VALUES, VALUES.replace('usage.get("cached_input_tokens", 0))',
                                   'usage.get("cached_input_tokens", 0),\n'
                                   '                      usage.get("cache_write_input_tokens", 0))'))(ws)
    replace(OLD, "    return totals, failed, None\n")(ws)


(T / "hidden" / "cases.json").write_text(json.dumps({"module": "bench_fixtures.cx", "cases": [
    {"id": c, "function": "report", "args": [events]} for c, events, _ in CASES]}, indent=1) + "\n")
(T / "expected" / "expected.json").write_text(json.dumps({c: {"value": w} for c, _, w in CASES}, indent=1) + "\n")
(T / "reference" / "zero_fill.patch").write_bytes(diff(zero_fill))
(T / "reference" / "noop.patch").write_bytes(b"")
(T / "reference" / "test_deletion.patch").write_bytes(diff(lambda ws: (ws / "tests/test_agent_cli.py").unlink()))
print(len(CASES), "cases; zero_fill + good, noop, test_deletion")
