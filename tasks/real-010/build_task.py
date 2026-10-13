"""Builds tasks/real-010 hidden cases, expected values and the non-trivial reference patches (run from the repo root).

good.patch is the real diff of python-humanize 823ad60 (src only). Cases run through the task-owned helper
base/bench_fixtures/hz.py (humanize imports itself as `humanize`, so it puts src/ on sys.path).
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

T = Path("tasks/real-010").resolve()
CASES = [  # (id, args to naturalsize(value, binary, gnu, format), expected value)
    ("default_reported", [999999], "1.0 MB"),
    ("default_edge", [999950], "1.0 MB"),
    ("negative", [-999999], "-1.0 MB"),
    ("binary", [1048575, True], "1.0 MiB"),
    ("gnu", [1048575, False, True], "1.0M"),
    ("format_no_decimals", [999500, False, False, "%.0f"], "1 MB"),
    ("format_two_decimals", [999999999, False, False, "%.2f"], "1.00 GB"),
    ("guard_below_edge", [999949], "999.9 kB"),
    ("guard_more_precision", [999999, False, False, "%.3f"], "999.999 kB"),
    ("guard_no_decimals_below", [999499, False, False, "%.0f"], "999 kB"),
    ("guard_binary_below", [1048064, True], "1023.5 KiB"),
    ("guard_largest_unit", [10 ** 30], "1.0 QB"),
]
OLD = "    exp = int(min(log(abs_bytes, base), len(suffix)))\n"
VARIANTS = {
    # threshold tuned for the reported default (%.1f, decimal): wrong for other formats and for binary
    "threshold_default": OLD + "    if exp < len(suffix) and abs_bytes / (base**exp) >= 999.95:\n        exp += 1\n",
    # rounds to one decimal regardless of the requested format
    "round_one_decimal": OLD + "    if exp < len(suffix) and round(abs_bytes / (base**exp), 1) >= base:\n        exp += 1\n",
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


(T / "hidden" / "cases.json").write_text(json.dumps({"module": "bench_fixtures.hz", "cases": [
    {"id": c, "function": "naturalsize", "args": a} for c, a, _ in CASES]}, indent=1) + "\n")
(T / "expected" / "expected.json").write_text(json.dumps({c: {"value": w} for c, _, w in CASES}, indent=1) + "\n")
for name, new in VARIANTS.items():
    def edit(ws, new=new):
        p = ws / "src/humanize/filesize.py"
        s = p.read_text()
        assert s.count(OLD) == 1
        p.write_text(s.replace(OLD, new, 1))
    (T / "reference" / f"{name}.patch").write_bytes(diff(edit))
(T / "reference" / "noop.patch").write_bytes(b"")
(T / "reference" / "test_deletion.patch").write_bytes(diff(lambda ws: (ws / "tests" / "test_filesize.py").unlink()))
print(len(CASES), "cases;", ", ".join(VARIANTS), "+ noop, test_deletion")
