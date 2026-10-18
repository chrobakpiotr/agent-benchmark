"""Builds tasks/real-014 hidden cases, expected values and the non-trivial reference patches (run from the repo root).

good.patch is the real diff of pypa/packaging 2602dd0 (src/ only). Expected values were taken from the fixed tree. The
bug cases are line breaks only: the base's own tests already reject a requirement suffixed with a line break, and the
grammar's whitespace is space and tab. Other whitespace (form feed, vertical tab, Unicode spaces) is left out, because
rejecting it is a choice the base does not document.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

T = Path("tasks/real-014").resolve()
INVALID = {"raises": "InvalidRequirement"}
URL = "https://example.com/pkg-1.0-py3-none-any.whl"
CASES = [  # (id, requirement text, expected)
    ("lf_inside_url", f"pkg @ {URL}\nother==2", INVALID),
    ("cr_inside_url", f"pkg @ {URL}\rother==2", INVALID),
    ("crlf_inside_url", f"pkg @ {URL}\r\nother==2", INVALID),
    ("crlf_after_url", f"pkg @ {URL}\r\n", INVALID),
    ("lf_before_marker", f'pkg @ {URL}\n ; os_name == "nt"', INVALID),
    ("guard_trailing_space", f"pkg @ {URL} ", {"value": ["pkg", URL, [], "", None]}),
    ("guard_trailing_tab", f"pkg @ {URL}\t", {"value": ["pkg", URL, [], "", None]}),
    ("guard_marker_after_space", f'pkg @ {URL} ; os_name == "nt"', {"value": ["pkg", URL, [], "", 'os_name == "nt"']}),
    ("guard_marker_after_tab", f'pkg @ {URL}\t; os_name == "nt"', {"value": ["pkg", URL, [], "", 'os_name == "nt"']}),
    ("guard_extras_file_url", "pkg[a,b] @ file:///tmp/a%20b.whl",
     {"value": ["pkg", "file:///tmp/a%20b.whl", ["a", "b"], "", None]}),
    ("guard_specifier", "pkg>=1,<2", {"value": ["pkg", None, [], "<2,>=1", None]}),
]
OLD = '    "URL": re.compile(r"\\S+"),\n'
VARIANTS = {
    # only the reported character
    "lf_only": '    "URL": re.compile(r"[^ \\t\\n]+"),\n',
    # strips the line break instead of rejecting it
    "strip_url": None,
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


def lf_only(ws):
    subprocess.run(["git", "apply", str(T / "reference" / "good.patch")], cwd=ws, env=ENV, check=True)
    p = ws / "src/packaging/_tokenizer.py"
    s = p.read_text()
    assert s.count(OLD) == 1
    p.write_text(s.replace(OLD, VARIANTS["lf_only"], 1))


def strip_url(ws):
    p = ws / "src/packaging/requirements.py"
    s = p.read_text()
    old = "        self.url: str | None = parsed.url or None\n"
    assert s.count(old) == 1
    p.write_text(s.replace(old, "        self.url: str | None = parsed.url.split()[0] if parsed.url else None\n", 1))


(T / "hidden" / "cases.json").write_text(json.dumps({"module": "bench_fixtures.req", "cases": [
    {"id": c, "function": "req", "args": [text]} for c, text, _ in CASES]}, indent=1) + "\n")
(T / "expected" / "expected.json").write_text(json.dumps({c: w for c, _, w in CASES}, indent=1) + "\n")
(T / "reference" / "lf_only.patch").write_bytes(diff(lf_only))
(T / "reference" / "strip_url.patch").write_bytes(diff(strip_url))
(T / "reference" / "noop.patch").write_bytes(b"")
(T / "reference" / "test_deletion.patch").write_bytes(diff(lambda ws: (ws / "tests/test_requirements.py").unlink()))
print(len(CASES), "cases; lf_only, strip_url + good, noop, test_deletion")
