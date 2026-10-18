"""Builds tasks/real-015 hidden cases, expected values and the non-trivial reference patches (run from the repo root).

good.patch is the real diff of mistune 86f9fd1 (src/ only). Expected outputs were taken from the fixed tree. Each case
is a table, or is not one, exactly as markdown-it-py's GFM tables decide. Inputs where the two disagree (a single-dash
cell, an empty delimiter cell) are left out.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

T = Path("tasks/real-015").resolve()
TABLE_AB = '<table>\n<thead>\n<tr>\n  <th>a</th>\n  <th>b</th>\n</tr>\n</thead>\n<tbody>\n</tbody>\n</table>\n'
CASES = [  # (id, markdown source, expected HTML from the fixed tree; table or not as markdown-it-py's GFM tables)
    ('text_rows_other_words', 'a | b\nfoo | bar\n1 | 2', '<p>a | b\nfoo | bar\n1 | 2</p>\n'),
    ('bordered_text_row', '| a | b |\n| x | y |', '<p>| a | b |\n| x | y |</p>\n'),
    ('one_cell_text', 'a | b\n:-: | x', '<p>a | b\n:-: | x</p>\n'),
    ('spaced_dashes', 'a | b\n-- - | ---', '<p>a | b\n-- - | ---</p>\n'),
    ('colons_only', 'a | b\n:: | ---', '<p>a | b\n:: | ---</p>\n'),
    ('single_colon', 'a | b\n--- | :', '<p>a | b\n--- | :</p>\n'),
    ('equals_signs', 'a | b\n=== | ===', '<p>a | b\n=== | ===</p>\n'),
    ('guard_plain', 'a | b\n--- | ---', TABLE_AB),
    ('guard_aligned', 'a | b\n:-- | --:', '<table>\n<thead>\n<tr>\n  <th style="text-align:left">a</th>\n'
     '  <th style="text-align:right">b</th>\n</tr>\n</thead>\n<tbody>\n</tbody>\n</table>\n'),
    ('guard_with_body', 'a | b\n---|---\n1 | 2', '<table>\n<thead>\n<tr>\n  <th>a</th>\n  <th>b</th>\n</tr>\n</thead>\n'
     '<tbody>\n<tr>\n  <td>1</td>\n  <td>2</td>\n</tr>\n</tbody>\n</table>\n'),
    ('guard_bordered', '| a |\n| --- |', '<table>\n<thead>\n<tr>\n  <th>a</th>\n</tr>\n</thead>\n<tbody>\n</tbody>\n</table>\n'),
    ('guard_padded', 'a | b\n --- | --- ', TABLE_AB),
]
OLD = "        else:\n            aligns.append(None)\n"
VARIANTS = {
    # rejects cells with letters or digits only: punctuation-only cells still pass
    "no_alnum": "        elif any(ch.isalnum() for ch in v):\n            return None, None\n" + OLD,
    # requires a dash somewhere in the cell: spaced dashes and mixed punctuation still pass
    "needs_dash": "        elif '-' not in v and v.strip():\n            return None, None\n" + OLD,
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


(T / "hidden" / "cases.json").write_text(json.dumps({"module": "bench_fixtures.md", "cases": [
    {"id": c, "function": "table_html", "args": [src]} for c, src, _ in CASES]}, indent=1) + "\n")
(T / "expected" / "expected.json").write_text(json.dumps({c: {"value": w} for c, _, w in CASES}, indent=1) + "\n")
for name, new in VARIANTS.items():
    def edit(ws, new=new):
        p = ws / "src/mistune/plugins/table.py"
        s = p.read_text()
        assert s.count(OLD) == 1
        p.write_text(s.replace(OLD, new, 1))
    (T / "reference" / f"{name}.patch").write_bytes(diff(edit))
(T / "reference" / "noop.patch").write_bytes(b"")
(T / "reference" / "test_deletion.patch").write_bytes(diff(lambda ws: (ws / "tests/test_plugins.py").unlink()))
print(len(CASES), "cases;", ", ".join(VARIANTS), "+ good, noop, test_deletion")
