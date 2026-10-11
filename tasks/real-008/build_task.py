"""Builds tasks/real-008 hidden cases, expected values and the non-trivial reference patches (run from the repo root).

good.patch is the real diff of python-semver 1d51591 (src only). The other patches are one per plausible reading;
`int_limit_off` is a different but correct fix and must PASS.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

T = Path("tasks/real-008").resolve()
L, BIG, NINES = "9" * 5000, "1" + "0" * 5000, "9" * 4999
CASES = [  # (id, args to src.semver.compare, expected)
    ("long_vs_short_reported", ["1.0.0-alpha." + L, "1.0.0-alpha.1"], 1),
    ("long_vs_short_reversed", ["1.0.0-alpha.1", "1.0.0-alpha." + L], -1),
    ("long_magnitude_by_length", ["1.0.0-a." + BIG, "1.0.0-a." + NINES], 1),
    ("long_equal", ["1.0.0-a." + L, "1.0.0-a." + L], 0),
    ("long_numeric_below_alphanumeric", ["1.0.0-a." + L, "1.0.0-a.x"], -1),
    ("guard_short_numeric", ["1.0.0-alpha.2", "1.0.0-alpha.10"], -1),
    ("guard_spec_order", ["1.0.0-alpha.beta", "1.0.0-beta"], -1),
    ("guard_release_above_rc", ["1.0.0", "1.0.0-rc.1"], 1),
]
OLD = ('        a_parts = [int(x) if x.isdigit() else x for x in (a or "").split(".")]\n'
       '        b_parts = [int(x) if x.isdigit() else x for x in (b or "").split(".")]\n')
VARIANTS = {
    # the report shows a ValueError: catch it and keep the identifier as text
    "catch_as_string": ("src/semver/version.py", OLD, OLD.replace("int(x) if x.isdigit() else x", "_num(x)").replace(
        "        a_parts", "        def _num(x):\n            try:\n                return int(x) if x.isdigit() else x\n"
        "            except ValueError:\n                return x\n\n        a_parts", 1)),
    # avoid int(): compare digit identifiers as text, still below alphanumerics
    "lexicographic_digits": ("src/semver/version.py", OLD, OLD.replace(
        "[int(x) if x.isdigit() else x", "[(0, x) if x.isdigit() else (1, x)")),
    # lift the interpreter's limit for the whole process: different but correct for these inputs
    "int_limit_off": ("src/semver/version.py", "import re\n", "import re\nimport sys\n\nsys.set_int_max_str_digits(0)\n"),
    # refuse huge identifiers instead of ordering them
    "reject_long": ("src/semver/version.py", OLD, OLD.replace("        a_parts", "        if any(len(x) > 4300 for x in "
        "(a or \"\").split(\".\") + (b or \"\").split(\".\")):\n            raise ValueError(\"prerelease identifier too long\")\n"
        "        a_parts", 1)),
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


(T / "hidden" / "cases.json").write_text(json.dumps({"module": "src.semver", "cases": [
    {"id": c, "function": "compare", "args": a} for c, a, _ in CASES]}, indent=1) + "\n")
(T / "expected" / "expected.json").write_text(json.dumps({c: {"value": w} for c, _, w in CASES}, indent=1) + "\n")
for name, (path, old, new) in VARIANTS.items():
    def edit(ws, path=path, old=old, new=new):
        p = ws / path
        s = p.read_text()
        assert s.count(old) == 1, (name, old[:40])
        p.write_text(s.replace(old, new, 1))
    (T / "reference" / f"{name}.patch").write_bytes(diff(edit))
(T / "reference" / "noop.patch").write_bytes(b"")
(T / "reference" / "test_deletion.patch").write_bytes(diff(lambda ws: (ws / "tests" / "test_compare.py").unlink()))
print(len(CASES), "cases;", ", ".join(VARIANTS), "+ noop, test_deletion")
