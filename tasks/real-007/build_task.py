"""Builds tasks/real-007 hidden cases, expected values and the non-trivial reference patches (run from the repo root).

good.patch is the real diff of pypa/packaging f14a093 (src only). The other patches are one per plausible reading;
`ascii_flag_global` is a different but correct fix and must PASS.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

T = Path("tasks/real-007").resolve()
BAD_SPEC, BAD_REQ = {"raises": "InvalidSpecifier"}, {"raises": "InvalidRequirement"}
CASES = [  # (id, function in src.packaging.requirements, args, expected)
    ("post_long_s_reported", "SpecifierSet", ["~=1.0.poſt1"], BAD_SPEC),
    ("post_long_s_in_set", "SpecifierSet", [">=1,~=2.0.poſt3"], BAD_SPEC),
    ("post_long_s_requirement", "Requirement", ["pkg~=1.0.poſt1"], BAD_REQ),
    ("pre_dotless_i", "SpecifierSet", ["~=1.0.prevıew1"], BAD_SPEC),
    ("pre_dotted_capital_i", "SpecifierSet", ["~=1.0.prevİew1"], BAD_SPEC),
    # Valid specifiers through the Specifier regex: the driver cannot serialise a SpecifierSet, so construction
    # succeeds exactly when the recorded exception is the driver's own TypeError (documented sentinel).
    ("valid_upper_rc", "SpecifierSet", ["~=1.0RC1"], {"raises": "TypeError"}),
    ("valid_upper_dev", "SpecifierSet", ["~=1.0.DEV1"], {"raises": "TypeError"}),
    ("valid_preview", "SpecifierSet", ["~=1.0.preview1"], {"raises": "TypeError"}),
    ("guard_post", "_parse_requirement", ["pkg~=1.0.post1"], {"value": ["pkg", "", [], "~=1.0.post1", None]}),
    ("guard_upper_rc", "_parse_requirement", ["pkg~=1.0RC1"], {"value": ["pkg", "", [], "~=1.0RC1", None]}),
    ("guard_upper_dev", "_parse_requirement", ["pkg~=1.0.DEV1"], {"value": ["pkg", "", [], "~=1.0.DEV1", None]}),
    ("guard_preview", "_parse_requirement", ["pkg~=1.0.preview1"], {"value": ["pkg", "", [], "~=1.0.preview1", None]}),
]
SPEC = "src/packaging/specifiers.py"
POST = "                (?:                                   # post release\n"
FLAGS = "re.VERBOSE | re.IGNORECASE\n"
VARIANTS = {
    "post_only": (POST, POST.replace("(?:", "(?a:", 1)),                     # the report names post only
    "no_ignorecase": (FLAGS, "re.VERBOSE\n"),                                # rejects legitimate upper-case forms
    "ascii_flag_global": (FLAGS, "re.VERBOSE | re.IGNORECASE | re.ASCII\n"),  # different but correct
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
for name, (old, new) in VARIANTS.items():
    def edit(ws, old=old, new=new):
        p = ws / SPEC
        s = p.read_text()
        assert s.count(old) == 1, (name, old)
        p.write_text(s.replace(old, new, 1))
    (T / "reference" / f"{name}.patch").write_bytes(diff(edit))
(T / "reference" / "noop.patch").write_bytes(b"")
(T / "reference" / "test_deletion.patch").write_bytes(diff(lambda ws: (ws / "tests" / "test_specifiers.py").unlink()))
print(len(CASES), "cases;", ", ".join(VARIANTS), "+ noop, test_deletion")
