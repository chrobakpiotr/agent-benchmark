"""Builds tasks/real-005 hidden cases, expected values and the non-trivial reference patches (run from the repo root).

good.patch is the real diff of pypa/packaging 2aada00 (src only). The other patches are one per plausible reading.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

T = Path("tasks/real-005").resolve()
CASES = [  # (id, function in src.packaging.requirements, args, expected)
    ("requirement_empty", "Requirement", ["pkg==="], {"raises": "InvalidRequirement"}),
    ("requirement_empty_spaced", "Requirement", ["pkg === "], {"raises": "InvalidRequirement"}),
    ("requirement_empty_in_list", "Requirement", ["pkg>=2,==="], {"raises": "InvalidRequirement"}),
    ("specifierset_empty", "SpecifierSet", ["==="], {"raises": "InvalidSpecifier"}),
    ("specifierset_empty_in_list", "SpecifierSet", [">=1,==="], {"raises": "InvalidSpecifier"}),
    ("parse_arbitrary_word", "_parse_requirement", ["pkg===anything"],
     {"value": ["pkg", "", [], "===anything", None]}),
    ("parse_arbitrary_in_list", "_parse_requirement", ["pkg>=1,===local+thing"],
     {"value": ["pkg", "", [], ">=1,===local+thing", None]}),
]
REGEX_OLD = "                [^\\s;)]*  # The arbitrary version can be just about anything,"
INIT_OLD = "            raise InvalidRequirement(str(e)) from e\n        self.marker: Marker | None = None\n"
VARIANTS = {
    # the report names Requirement only: reject an empty === there and nowhere else
    "requirement_only": ("src/packaging/requirements.py", INIT_OLD, INIT_OLD.replace(
        "        self.marker:", "        if any(s.operator == \"===\" and not s.version for s in self.specifier):\n"
        "            raise InvalidRequirement(\"=== needs a version\")\n        self.marker:", 1)),
    # === must look like a version (starts with a digit): rejects legitimate arbitrary strings
    "overstrict": ("src/packaging/specifiers.py", REGEX_OLD,
                   "                \\d[^\\s;)]*  # The arbitrary version can be just about anything,"),
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


(T / "hidden" / "cases.json").write_text(json.dumps({"module": "src.packaging.requirements", "cases": [
    {"id": c, "function": f, "args": a} for c, f, a, _ in CASES]}, indent=1) + "\n")
(T / "expected" / "expected.json").write_text(json.dumps({c: w for c, _, _, w in CASES}, indent=1) + "\n")
for name, (path, old, new) in VARIANTS.items():
    def edit(ws, path=path, old=old, new=new):
        p = ws / path
        s = p.read_text()
        assert old in s, (name, old)
        p.write_text(s.replace(old, new, 1))
    (T / "reference" / f"{name}.patch").write_bytes(diff(edit))
(T / "reference" / "test_deletion.patch").write_bytes(diff(lambda ws: (ws / "tests" / "test_specifiers.py").unlink()))
print(len(CASES), "cases;", ", ".join(VARIANTS), "+ test_deletion")
