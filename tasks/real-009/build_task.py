"""Builds tasks/real-009 hidden cases, expected values and the non-trivial reference patches (run from the repo root).

good.patch is the real diff of python-semver 0aa17a3 (src only). Cases call base/bench_fixtures/ops.py, a task-owned
helper outside the patch scope that applies Python's comparison operators to Version.parse(version).
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

T = Path("tasks/real-009").resolve()
TYPEERROR = {"raises": "TypeError"}
CASES = [  # (id, function in bench_fixtures.ops, args, expected); only malformed structures (TypeError at the base):
    # non-numeric parts raise ValueError like an invalid version string, which the library keeps raising (v1 defect)
    ("eq_empty_dict_reported", "eq", ["1.2.3", {}], {"value": False}),
    ("eq_unknown_key", "eq", ["1.2.3", {"major": 1, "foo": 2}], {"value": False}),
    ("ne_unknown_key", "ne", ["1.2.3", {"major": 1, "foo": 2}], {"value": True}),
    ("ne_empty_dict", "ne", ["1.2.3", {}], {"value": True}),
    ("lt_empty_dict", "lt", ["1.2.3", {}], TYPEERROR),
    ("gt_unknown_key", "gt", ["1.2.3", {"major": 1, "foo": 2}], TYPEERROR),
    ("guard_eq_tuple", "eq", ["1.2.3", [1, 2, 3]], {"value": True}),
    ("guard_eq_short_list", "eq", ["1.2.3", [1, 2]], {"value": False}),
    ("guard_lt_dict", "lt", ["1.2.3", {"major": 2, "minor": 0, "patch": 0}], {"value": True}),
    ("guard_gt_list", "gt", ["1.2.3", [1, 0, 0]], {"value": True}),
]
OLD = "        return operator(self, other)\n\n    return wrapper\n"
VARIANTS = {
    # the report shows == raising: swallow the error and answer False for every operator
    "catch_return_false": OLD.replace("        return operator(self, other)\n",
                                      "        try:\n            return operator(self, other)\n"
                                      "        except (TypeError, ValueError):\n            return False\n", 1),
    # catch only the structural TypeError and hand it to Python's operand protocol: a correct alternative in v2
    "notimplemented_on_typeerror": OLD.replace("        return operator(self, other)\n",
                                               "        try:\n            return operator(self, other)\n"
                                               "        except TypeError:\n            return NotImplemented\n", 1),
    # turn every internal error into a TypeError, also for == and !=
    "raise_typeerror": OLD.replace("        return operator(self, other)\n",
                                   "        try:\n            return operator(self, other)\n"
                                   "        except (TypeError, ValueError) as error:\n"
                                   "            raise TypeError(f\"cannot compare Version with {other!r}\") from error\n", 1),
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


(T / "hidden" / "cases.json").write_text(json.dumps({"module": "bench_fixtures.ops", "cases": [
    {"id": c, "function": f, "args": a} for c, f, a, _ in CASES]}, indent=1) + "\n")
(T / "expected" / "expected.json").write_text(json.dumps({c: w for c, _, _, w in CASES}, indent=1) + "\n")
for name, new in VARIANTS.items():
    def edit(ws, new=new):
        p = ws / "src/semver/version.py"
        s = p.read_text()
        assert s.count(OLD) == 1
        p.write_text(s.replace(OLD, new, 1))
    (T / "reference" / f"{name}.patch").write_bytes(diff(edit))
(T / "reference" / "noop.patch").write_bytes(b"")
(T / "reference" / "test_deletion.patch").write_bytes(diff(lambda ws: (ws / "tests" / "test_compare.py").unlink()))
print(len(CASES), "cases;", ", ".join(VARIANTS), "+ noop, test_deletion")
