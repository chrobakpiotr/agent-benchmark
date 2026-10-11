"""Builds tasks/real-006 hidden cases, expected values and the non-trivial reference patches (run from the repo root).

good.patch is the real diff of pypa/packaging d3e7f5d (src only). The other patches are one per plausible reading.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

T = Path("tasks/real-006").resolve()
INVALID = {"raises": "InvalidVersion"}
CASES = [  # (id, function in src.packaging.utils, args, expected)
    ("float_reported", "Version", [1.0], INVALID),
    ("int", "Version", [7], INVALID),
    ("none", "Version", [None], INVALID),
    ("list_of_str", "Version", [["1"]], INVALID),          # takes the AttributeError path at the base
    ("list_two_parts", "Version", [["1", "2"]], INVALID),
    ("dict", "Version", [{"major": 1}], INVALID),
    ("bad_string_unchanged", "Version", ["not a version"], INVALID),
    ("canonical_simple", "canonicalize_version", ["1.0.0"], {"value": "1"}),
    ("canonical_complex", "canonicalize_version", ["2!1.0.post0.dev1"], {"value": "2!1.post0.dev1"}),
]
OLD = "        if _SIMPLE_VERSION_INDICATORS.issuperset(version):\n"
VARIANTS = {
    # the report names a float only
    "float_only": OLD.replace("        if", "        if isinstance(version, float):\n"
                              "            raise InvalidVersion(f\"Invalid version: {version!r}\")\n        if", 1),
    # the report names a TypeError only: catch that one, miss the AttributeError path
    "catch_typeerror": ("        try:\n            _simple = _SIMPLE_VERSION_INDICATORS.issuperset(version)\n"
                        "            self._regex.fullmatch(version) if not _simple else None\n"
                        "        except TypeError:\n            raise InvalidVersion(f\"Invalid version: {version!r}\") from None\n"
                        + OLD),
    # make a float work instead of failing (contradicts the report's expected InvalidVersion)
    "coerce_to_str": "        if not isinstance(version, str):\n            version = str(version)\n" + OLD,
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


(T / "hidden" / "cases.json").write_text(json.dumps({"module": "src.packaging.utils", "cases": [
    {"id": c, "function": f, "args": a} for c, f, a, _ in CASES]}, indent=1) + "\n")
(T / "expected" / "expected.json").write_text(json.dumps({c: w for c, _, _, w in CASES}, indent=1) + "\n")
for name, new in VARIANTS.items():
    def edit(ws, new=new):
        p = ws / "src/packaging/version.py"
        s = p.read_text()
        assert s.count(OLD) == 1
        p.write_text(s.replace(OLD, new, 1))
    (T / "reference" / f"{name}.patch").write_bytes(diff(edit))
(T / "reference" / "noop.patch").write_bytes(b"")
(T / "reference" / "test_deletion.patch").write_bytes(diff(lambda ws: (ws / "tests" / "test_version.py").unlink()))
print(len(CASES), "cases;", ", ".join(VARIANTS), "+ noop, test_deletion")
