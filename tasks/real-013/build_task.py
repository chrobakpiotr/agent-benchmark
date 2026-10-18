"""Builds tasks/real-013 hidden cases, expected values and the non-trivial reference patches (run from the repo root).

good.patch is the real diff of mistune 2d26bc8 (src/ only). Expected outputs were taken from the fixed tree; every one
also matches the CommonMark reference implementation (commonmark.py 0.9.1), so none depends on a mistune-only reading.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

T = Path("tasks/real-013").resolve()
CASES = [  # (id, markdown source, expected HTML from the fixed tree; each checked against commonmark.py 0.9.1)
    ('reported_shape_other_text', '*a***a*', '<p><em>a</em>*<em>a</em></p>\n'),
    ('in_sentence', 'x *a***a* y', '<p>x <em>a</em>*<em>a</em> y</p>\n'),
    ('strong_closer_remainder', '**a***a**', '<p><strong>a</strong><em>a</em>*</p>\n'),
    ('opener_run_consumed_first', 'a***b*c*', '<p>a*<em><em>b</em>c</em></p>\n'),
    ('opener_run_triple', '***a*a*a', '<p>*<em><em>a</em>a</em>a</p>\n'),
    ('double_opener_single_closer', '**a* a*a', '<p>*<em>a</em> a*a</p>\n'),
    ('underscore_content', '*_***_*', '<p><em>_</em>*<em>_</em></p>\n'),
    ('closer_run_consumed_first', 'a*a *a**', '<p>a*a <em>a</em>*</p>\n'),
    ('closer_run_triple', '*a *a***a', '<p><em>a <em>a</em></em>*a</p>\n'),
    ('guard_four_star_middle', '*a****a*', '<p><em>a</em>**<em>a</em></p>\n'),
    ('guard_alternating', '*a***a***a*', '<p><em>a</em><strong>a</strong><em>a</em></p>\n'),
    ('guard_triple_both', '***a***', '<p><em><strong>a</strong></em></p>\n'),
    ('guard_nested_strong', '*a **b** c*', '<p><em>a <strong>b</strong> c</em></p>\n'),
    ('guard_underscore_intraword', '_foo___bar_', '<p><em>foo___bar</em></p>\n'),
    ('guard_spec_rule_9', '*foo**bar***baz*', '<p><em>foo<strong>bar</strong></em>baz*</p>\n'),
]
FIXED = "        open_len = opener.orig_length\n        close_len = closer.orig_length\n"
VARIANTS = {
    # original length only for the closer: misses runs that were consumed as openers
    "closer_only": "        open_len = opener.length\n        close_len = closer.orig_length\n",
    # original length only for the opener
    "opener_only": "        open_len = opener.orig_length\n        close_len = closer.length\n",
    # drops the multiple-of-3 rule altogether
    "no_rule": "        return True\n        open_len = close_len = 0\n",
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


def good_then(new):
    def edit(ws):
        subprocess.run(["git", "apply", str(T / "reference" / "good.patch")], cwd=ws, env=ENV, check=True)
        p = ws / "src/mistune/inline_parser.py"
        s = p.read_text()
        assert s.count(FIXED) == 1
        p.write_text(s.replace(FIXED, new, 1))
    return edit


(T / "hidden" / "cases.json").write_text(json.dumps({"module": "bench_fixtures.md", "cases": [
    {"id": c, "function": "html", "args": [src]} for c, src, _ in CASES]}, indent=1) + "\n")
(T / "expected" / "expected.json").write_text(json.dumps({c: {"value": w} for c, _, w in CASES}, indent=1) + "\n")
for name, new in VARIANTS.items():
    (T / "reference" / f"{name}.patch").write_bytes(diff(good_then(new)))
(T / "reference" / "noop.patch").write_bytes(b"")
(T / "reference" / "test_deletion.patch").write_bytes(diff(lambda ws: (ws / "tests/test_commonmark.py").unlink()))
print(len(CASES), "cases;", ", ".join(VARIANTS), "+ good, noop, test_deletion")
