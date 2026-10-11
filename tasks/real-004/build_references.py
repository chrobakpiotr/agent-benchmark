"""Builds the non-trivial reference patches of tasks/real-004 (run from the repo root); good.patch is the real diff.

One patch per plausible reading of the bug report; each is a `git diff` of an edited copy of base/.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

T = Path("tasks/real-004").resolve()
ANCHOR = '            raise ContractError("BINDING_MISMATCH", f"qualification evidence {ref[\'path\']}")\n    return doc\n'
READ = "(root / r['path']).resolve().read_bytes()"
PER_CHECK = ("    job = doc['tuple']['job_id'].encode()\n"
             "    for check in doc['checks']:\n"
             f"        if check['result'] == 'pass' and not any({{test}} for r in check['evidence']):\n"
             "            raise ContractError('BINDING_MISMATCH', 'evidence does not name the job')\n")
ANY_CHECK = ("    job = doc['tuple']['job_id'].encode()\n"
             f"    if not any(job in {READ} for c in doc['checks'] if c['result'] == 'pass' for r in c['evidence']):\n"
             "        raise ContractError('BINDING_MISMATCH', 'evidence does not name the job')\n")
REVIEW = ("    review = doc['independent_review']\n"
          "    if review is not None and review['subject'].encode() not in "
          "(root / review['evidence']['path']).resolve().read_bytes():\n"
          "        raise ContractError('BINDING_MISMATCH', 'review evidence does not name the subject')\n")
VARIANTS = {
    "job_only": PER_CHECK.format(test=f"job in {READ}"),            # relabelling reading: forgets the review
    "job_any": ANY_CHECK + REVIEW,                                 # one check naming the job is enough
    "overstrict": PER_CHECK.format(test=f"re.search(rb'(?m) ' + re.escape(job) + rb'$', {READ})") + REVIEW,
}
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
       "GIT_AUTHOR_NAME": "x", "GIT_AUTHOR_EMAIL": "x@x", "GIT_COMMITTER_NAME": "x", "GIT_COMMITTER_EMAIL": "x@x"}


def patch(name, edit):
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d) / "ws"
        shutil.copytree(T / "base", ws)
        for argv in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "base"]):
            subprocess.run(["git", *argv], cwd=ws, env=ENV, check=True, capture_output=True)
        edit(ws)
        subprocess.run(["git", "add", "-A"], cwd=ws, env=ENV, check=True)
        diff = subprocess.run(["git", "diff", "--cached"], cwd=ws, env=ENV, check=True, capture_output=True).stdout
        (T / "reference" / f"{name}.patch").write_bytes(diff)


for name, block in VARIANTS.items():
    def edit(ws, block=block):
        p = ws / "src/agent_harness/contract.py"
        s = p.read_text()
        assert ANCHOR in s
        p.write_text(s.replace(ANCHOR, ANCHOR.replace("    return doc\n", block + "    return doc\n"), 1))
    patch(name, edit)
patch("test_deletion", lambda ws: (ws / "tests/test_qualification.py").unlink())
print(sorted(p.name for p in (T / "reference").iterdir()))
