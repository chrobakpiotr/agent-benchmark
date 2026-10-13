"""Builds tasks/real-011 hidden cases, expected values and the non-trivial reference patches (run from the repo root).

good.patch is the real diff of croniter f64665e (src/croniter/croniter.py). Cases run through the task-owned helper
base/bench_fixtures/cron.py, which puts the vendored python-dateutil and six (base/bench_fixtures/vendor, with their
licenses) and src/ on the path. Expected values were taken from the fixed tree and checked by hand.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

T = Path("tasks/real-011").resolve()
S = "2026-01-01T00:00:00"
CASES = [  # (id, cron expression, expected next three runs after S)
    ("minute_max_reported", "59/15 * * * *", ["2026-01-01T00:59:00", "2026-01-01T01:59:00", "2026-01-01T02:59:00"]),
    ("hour_max", "0 23/6 * * *", ["2026-01-01T23:00:00", "2026-01-02T23:00:00", "2026-01-03T23:00:00"]),
    ("day_of_month_max", "0 0 31/5 * *", ["2026-01-31T00:00:00", "2026-03-31T00:00:00", "2026-05-31T00:00:00"]),
    ("month_max", "0 0 1 DEC/3 *", ["2026-12-01T00:00:00", "2027-12-01T00:00:00", "2028-12-01T00:00:00"]),
    ("day_of_week_max", "0 0 * * SAT/2", ["2026-01-03T00:00:00", "2026-01-10T00:00:00", "2026-01-17T00:00:00"]),
    # croniter deliberately expands an explicit equal range to the whole cycle (comment in the code): keep it
    ("guard_explicit_equal_range", "0 0 1 JAN-JAN *", ["2026-02-01T00:00:00", "2026-03-01T00:00:00", "2026-04-01T00:00:00"]),
    ("guard_explicit_equal_range_step", "0 0 1 JAN-JAN/2 *", ["2026-03-01T00:00:00", "2026-05-01T00:00:00", "2026-07-01T00:00:00"]),
    ("guard_start_below_max", "58/15 * * * *", ["2026-01-01T00:58:00", "2026-01-01T01:58:00", "2026-01-01T02:58:00"]),
    ("guard_plain_step", "*/20 * * * *", ["2026-01-01T00:20:00", "2026-01-01T00:40:00", "2026-01-01T01:00:00"]),
]
OLD = ("                    elif low == high:\n                        rng = list(\n"
       "                            range(cls.RANGES[field_index][0], cls.RANGES[field_index][1] + 1, step)\n"
       "                        )\n")
VARIANTS = {
    # every equal range becomes one value: fixes the report, breaks the deliberate "Jan-Jan" whole cycle
    "equal_range_single": "                    elif low == high:\n                        rng = [low]\n",
    # only stepped equal ranges become one value: keeps Jan-Jan, breaks an explicit "JAN-JAN/2"
    "equal_range_with_step": ("                    elif low == high and step > 1:\n                        rng = [low]\n" + OLD),
}
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
       "GIT_AUTHOR_NAME": "x", "GIT_AUTHOR_EMAIL": "x@x", "GIT_COMMITTER_NAME": "x", "GIT_COMMITTER_EMAIL": "x@x"}


def diff(edit):
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d) / "ws"
        shutil.copytree(T / "base", ws)
        for argv in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "base"]):
            subprocess.run(["git", *argv], cwd=ws, env=ENV, check=True, capture_output=True)
        edit(ws)
        return subprocess.run(["git", "diff"], cwd=ws, env=ENV, check=True, capture_output=True).stdout


(T / "hidden" / "cases.json").write_text(json.dumps({"module": "bench_fixtures.cron", "cases": [
    {"id": c, "function": "next_runs", "args": [expr, S, 3]} for c, expr, _ in CASES]}, indent=1) + "\n")
(T / "expected" / "expected.json").write_text(json.dumps({c: {"value": w} for c, _, w in CASES}, indent=1) + "\n")
for name, new in VARIANTS.items():
    def edit(ws, new=new):
        p = ws / "src/croniter/croniter.py"
        s = p.read_text()
        assert s.count(OLD) == 1
        p.write_text(s.replace(OLD, new, 1))
    (T / "reference" / f"{name}.patch").write_bytes(diff(edit))
(T / "reference" / "noop.patch").write_bytes(b"")
(T / "reference" / "test_deletion.patch").write_bytes(diff(lambda ws: (ws / "src/croniter/tests/test_croniter.py").unlink()))
print(len(CASES), "cases;", ", ".join(VARIANTS), "+ noop, test_deletion")
