"""Independent graders. Each reads only the sealed candidate and the pinned task bundle.

The grader identity digest is this file's bytes, so any change to grading logic changes the recorded digest.

- sort-check: data-only candidate, never executed.
- patch-unittest: applies a patch to a fresh copy of the pinned base and runs the pinned hidden tests in a
  subprocess with a timeout and an empty environment. This executes candidate code on the host, so it is only
  allowed when the caller vouches for the candidate source (fake executor + reference patches). Model-generated
  patches need the isolated grading host of AB5-05b.
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath

from .schema import ValidationError, digest, verify_bundle

GRADER_VERSION = "1"
ISOLATION = {
    "sort-check": "none: in-process, data-only candidate, offline fake track (transparent diagnostic, no hidden tests)",
    "patch-unittest": ("host subprocess: temp workspace, empty env, timeout only; no CPU/memory/network limits; "
                       "hidden tests readable in the bundle (transparent diagnostic)"),
}


def identity(grader_id):
    return {"id": grader_id, "version": GRADER_VERSION, "digest": digest(Path(__file__).read_bytes())}


def _sealed(candidates_dir, candidate_digest):
    path = Path(candidates_dir) / candidate_digest.split(":", 1)[-1]
    data = path.read_bytes() if path.is_file() else None
    return data if data is not None and digest(data) == candidate_digest else None


def grade(task, candidates_dir, candidate_digest, bundle_dir=None, host_execution_allowed=False, timeout=None):
    """Return (result, criteria). INVALID = candidate or bundle cannot be bound to its pinned digest."""
    data = _sealed(candidates_dir, candidate_digest)
    criteria = [{"criterion": "candidate_matches_sealed_digest", "passed": data is not None}]
    if data is None:
        return "INVALID", criteria
    if task["grader"]["id"] == "sort-check":
        return _grade_sort(task, data, criteria)
    return _grade_patch(task, data, criteria, Path(bundle_dir), host_execution_allowed, timeout)


def _grade_sort(task, data, criteria):
    try:
        value = json.loads(data)
    except ValueError:
        value = None
    is_ints = isinstance(value, list) and all(isinstance(v, int) and not isinstance(v, bool) for v in value)
    criteria.append({"criterion": "is_list_of_integers", "passed": is_ints})
    criteria.append({"criterion": "permutation_of_input", "passed": is_ints and Counter(value) == Counter(task["input"])})
    criteria.append({"criterion": "non_decreasing", "passed": is_ints and all(a <= b for a, b in zip(value, value[1:]))})
    return ("PASS" if all(c["passed"] for c in criteria) else "FAIL"), criteria


PATH_LINE = re.compile(r"^(?:--- |\+\+\+ |rename from |rename to |copy from |copy to )(.+?)(?:\t.*)?$")


def patch_paths(text):
    """Every path a unified/git patch touches, with a/ b/ prefixes stripped."""
    paths = set()
    for line in text.splitlines():
        if line.startswith("diff --git "):
            paths.update(p[2:] if p[:2] in ("a/", "b/") else p for p in line[11:].split(" "))
            continue
        m = PATH_LINE.match(line)
        if m and m.group(1) != "/dev/null":
            p = m.group(1)
            paths.add(p[2:] if p[:2] in ("a/", "b/") else p)
    return paths


def _scope_violations(text, scope):
    bad = []
    if re.search(r"^(new|old|deleted) (file )?mode 120000", text, re.M):
        bad.append("symlink mode")
    for p in sorted(patch_paths(text)):
        pp = PurePosixPath(p)
        if pp.is_absolute() or ".." in pp.parts or p not in scope:
            bad.append(p)
    return bad


def _grade_patch(task, data, criteria, bundle_dir, host_execution_allowed, timeout):
    b = task["bundle"]
    try:
        verify_bundle(task, bundle_dir)
        bundle_ok = True
    except ValidationError:
        bundle_ok = False
    criteria.append({"criterion": "bundle_matches_pinned_digests", "passed": bundle_ok,
                     "detail": {"base": b["base_digest"], "hidden": b["hidden_digest"]}})
    if not bundle_ok:
        return "INVALID", criteria
    if not host_execution_allowed:
        criteria.append({"criterion": "host_execution_allowed", "passed": False,
                         "detail": "candidate source not vouched for; needs isolated grading host (AB5-05b)"})
        return "INVALID", criteria

    text = data.decode("utf-8", errors="replace")
    violations = _scope_violations(text, b["scope"])
    criteria.append({"criterion": "patch_within_scope", "passed": not violations, "detail": violations})
    if violations:
        return "FAIL", criteria

    with tempfile.TemporaryDirectory(prefix="ab-grade-") as tmp:
        tmp = Path(tmp)
        ws, hidden = tmp / "workspace", tmp / "hidden"
        shutil.copytree(bundle_dir / "base", ws)
        env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp), "PYTHONDONTWRITEBYTECODE": "1",
               "GIT_CONFIG_NOSYSTEM": "1", "GIT_CEILING_DIRECTORIES": str(tmp)}
        applies = True
        if text.strip():
            (tmp / "candidate.patch").write_bytes(data)
            subprocess.run(["git", "init", "-q"], cwd=ws, env=env, check=True)
            p = subprocess.run(["git", "apply", "--whitespace=nowarn", str(tmp / "candidate.patch")],
                               cwd=ws, env=env, capture_output=True, text=True)
            applies = p.returncode == 0
            shutil.rmtree(ws / ".git")
        criteria.append({"criterion": "patch_applies", "passed": applies})
        if not applies:
            return "FAIL", criteria

        shutil.copytree(bundle_dir / "hidden", hidden)  # outside the workspace, only after the patch is applied
        limit = timeout or b["timeout_seconds"]
        proc = subprocess.Popen([sys.executable, "-m", "unittest", "discover", "-s", str(hidden), "-t", str(hidden)],
                                cwd=ws, env={**env, "PYTHONPATH": str(ws)}, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            _, stderr = proc.communicate(timeout=limit)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)  # whole process group, not just the direct child
            proc.communicate()
            criteria.append({"criterion": "hidden_tests_finished_within_limit", "passed": False,
                             "detail": f"{limit}s"})
            return "FAIL", criteria
        criteria.append({"criterion": "hidden_tests_finished_within_limit", "passed": True})
        ran = re.search(r"^Ran (\d+) tests?", stderr, re.M)
        count = int(ran.group(1)) if ran else None
        criteria.append({"criterion": "hidden_test_count_matches", "passed": count == b["hidden_test_count"],
                         "detail": {"expected": b["hidden_test_count"], "ran": count}})
        criteria.append({"criterion": "hidden_tests_pass", "passed": proc.returncode == 0,
                         "detail": {"exit_code": proc.returncode, "output_digest": digest(stderr.encode())}})
    return ("PASS" if all(c["passed"] for c in criteria) else "FAIL"), criteria
