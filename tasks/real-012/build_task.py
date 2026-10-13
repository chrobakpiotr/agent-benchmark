"""Builds tasks/real-012 hidden cases, expected values and the non-trivial reference patches (run from the repo root).

good.patch is the real diff of Python-Markdown 7c265bc (markdown/ only). Expected outputs were taken from the fixed
tree and checked against the upstream tests of that commit.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

T = Path("tasks/real-012").resolve()
CASES = [  # (id, markdown source, expected HTML)
    ("code_span_path_reported", "Run `cmd 2</dev/null` here.\n\nThis paragraph should not disappear.",
     "<p>Run <code>cmd 2&lt;/dev/null</code> here.</p>\n<p>This paragraph should not disappear.</p>"),
    ("code_span_space_in_name", "`</ab c` z\n\nnext", "<p><code>&lt;/ab c</code> z</p>\n<p>next</p>"),
    ("code_span_trailing_slash", "`</dev/` > q\n\nnext", "<p><code>&lt;/dev/</code> &gt; q</p>\n<p>next</p>"),
    ("code_span_later_gt", "`</dev` z > q\n\nnext", "<p><code>&lt;/dev</code> z &gt; q</p>\n<p>next</p>"),
    ("plain_text_unterminated", "x </em y\n\nnext", "<p>x &lt;/em y</p>\n<p>next</p>"),
    ("guard_bare_slash", "a </ b\n\nnext", "<p>a &lt;/ b</p>\n<p>next</p>"),
    ("guard_real_end_tag", "<em>ok</em> fine\n\nnext", "<p><em>ok</em> fine</p>\n<p>next</p>"),
    ("guard_start_tag_in_code", "`<b>` code\n\nnext", "<p><code>&lt;b&gt;</code> code</p>\n<p>next</p>"),
    ("guard_less_than", "plain 2<3 text\n\nnext", "<p>plain 2&lt;3 text</p>\n<p>next</p>"),
]
OLD = "        return super().parse_endtag(i)\n\n    def parse_starttag"
VARIANTS = {
    # only the reported shape: an end tag that looks like a path ("</dev/...")
    "slash_path_only": ("        if re.match(r'</[A-Za-z]+/', self.rawdata[i:]):\n"
                        "            self.handle_data(self.rawdata[i:i + 2])\n            return i + 2\n" + OLD),
    # data only when no '>' follows at all: misses an unterminated tag with a later '>'
    "gt_lookahead": ("        if '>' not in self.rawdata[i:]:\n"
                     "            self.handle_data(self.rawdata[i:i + 2])\n            return i + 2\n" + OLD),
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


(T / "hidden" / "cases.json").write_text(json.dumps({"module": "markdown", "cases": [
    {"id": c, "function": "markdown", "args": [src]} for c, src, _ in CASES]}, indent=1) + "\n")
(T / "expected" / "expected.json").write_text(json.dumps({c: {"value": w} for c, _, w in CASES}, indent=1) + "\n")
for name, new in VARIANTS.items():
    def edit(ws, new=new):
        p = ws / "markdown/htmlparser.py"
        s = p.read_text()
        assert s.count(OLD) == 1 and "\nimport re\n" in s
        p.write_text(s.replace(OLD, new, 1))
    (T / "reference" / f"{name}.patch").write_bytes(diff(edit))
(T / "reference" / "noop.patch").write_bytes(b"")
(T / "reference" / "test_deletion.patch").write_bytes(diff(lambda ws: (ws / "tests/test_syntax/blocks/test_html_blocks.py").unlink()))
print(len(CASES), "cases;", ", ".join(VARIANTS), "+ noop, test_deletion")
