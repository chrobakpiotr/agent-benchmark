"""Independent graders. Each reads only the sealed candidate and the pinned task bundle.

The grader identity digest is this file's bytes, so any change to grading logic changes the recorded digest.

- sort-check: data-only candidate, never executed.
- patch-unittest: applies a patch to a fresh copy of the pinned base and runs the pinned hidden tests in a
  subprocess with a timeout and an empty environment. This executes candidate code on the host, so it is only
  allowed when the caller vouches for the candidate source (fake executor + reference patches). Model-generated
  patches need the isolated grading host of AB5-05b.
- patch-io: same pre-checks and patch step; then only the case inputs enter the candidate's process, a driver writes
  the candidate's answers to one bounded output file, and the verdict is computed here from that file against
  expected values that never enter the candidate's process. Exit code and output of that process are evidence
  only, so a candidate cannot forge a pass by printing or exiting early. Same host/vouching rule as patch-unittest.
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
    "patch-io": ("host subprocess: temp workspace, empty env, timeout only; no CPU/memory/network limits; only case "
                 "inputs enter the candidate process, verdict computed outside it from a bounded output file; "
                 "expected values stay readable on the host by path (transparent diagnostic)"),
}
OUTPUT_LIMIT = 1 << 20  # bytes of the candidate's output file (AB5-05b B9)

# Runs inside the candidate's process: inputs in, answers out. It never sees expected values.
DRIVER = """import importlib, json, sys
spec = json.load(open(sys.argv[1]))
mod = importlib.import_module(spec["module"])
out = {}
for case in spec["cases"]:
    try:
        out[case["id"]] = {"value": json.loads(json.dumps(getattr(mod, case["function"])(*case["args"])))}
    except Exception as exc:
        out[case["id"]] = {"raises": [k.__name__ for k in type(exc).__mro__]}
with open(sys.argv[2], "w") as f:
    json.dump(out, f)
"""


def identity(grader_id):
    return {"id": grader_id, "version": GRADER_VERSION, "digest": digest(Path(__file__).read_bytes())}


def _sealed(candidates_dir, candidate_digest):
    path = Path(candidates_dir) / candidate_digest.split(":", 1)[-1]
    data = path.read_bytes() if path.is_file() else None
    return data if data is not None and digest(data) == candidate_digest else None


def grade(task, candidates_dir, candidate_digest, bundle_dir=None, host_execution_allowed=False, timeout=None,
          qualified_run=None):
    """Return (result, criteria). INVALID = candidate or bundle cannot be bound to its pinned digest.

    `qualified_run` (patch-io only) replaces `run_cases` with a run on the qualified grading target, so candidates
    that are not vouched for can be graded without executing them on this host.
    """
    data = _sealed(candidates_dir, candidate_digest)
    criteria = [{"criterion": "candidate_matches_sealed_digest", "passed": data is not None}]
    if data is None:
        return "INVALID", criteria
    if task["grader"]["id"] == "sort-check":
        return _grade_sort(task, data, criteria)
    return _grade_patch(task, data, criteria, Path(bundle_dir), host_execution_allowed, timeout, qualified_run)


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


def _grade_patch(task, data, criteria, bundle_dir, host_execution_allowed, timeout, qualified_run=None):
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
    if qualified_run is not None and task["grader"]["id"] != "patch-io":
        criteria.append({"criterion": "qualified_grading_supported", "passed": False,
                         "detail": "only patch-io runs on the qualified target"})
        return "INVALID", criteria
    if not host_execution_allowed and qualified_run is None:
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

        if task["grader"]["id"] == "patch-io":
            return _grade_io(b, bundle_dir, ws, tmp / "run", env, timeout or b["timeout_seconds"], criteria,
                             qualified_run or run_cases)
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


def run_cases(ws, cases, run_dir, env, limit):
    """Run the patched workspace on the case inputs in a fresh process group; return (finished, exit_code, output).

    Only `cases` (inputs) enter the process. `output` is the bytes of its single output file (at most
    OUTPUT_LIMIT + 1; None if missing or a symlink). A qualified target will run this step as a contract launch and
    return the file through result.artifacts[] (AB5-05b B9).
    """
    run_dir.mkdir()
    (run_dir / "driver.py").write_text(DRIVER)
    (run_dir / "cases.json").write_bytes(cases)
    out = run_dir / "outputs.json"
    proc = subprocess.Popen([sys.executable, str(run_dir / "driver.py"), str(run_dir / "cases.json"), str(out)],
                            cwd=ws, env={**env, "PYTHONPATH": str(ws)}, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        proc.wait(timeout=limit)
        finished = True
    except subprocess.TimeoutExpired:
        finished = False
    try:
        os.killpg(proc.pid, signal.SIGKILL)  # leftovers of the group must not touch the output after this point
    except ProcessLookupError:
        pass
    proc.wait()
    if not finished:
        return False, None, None
    try:
        fd = os.open(out, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return True, proc.returncode, None
    with os.fdopen(fd, "rb") as f:
        return True, proc.returncode, f.read(OUTPUT_LIMIT + 1)


def _equal(a, b):
    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return a == b if num(a) and num(b) else json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _case_passes(got, want):
    if not isinstance(got, dict):
        return False
    if "raises" in want:
        return isinstance(got.get("raises"), list) and want["raises"] in got["raises"]
    return "value" in got and _equal(got["value"], want["value"])


def _grade_io(b, bundle_dir, ws, run_dir, env, limit, criteria, run=run_cases):
    expected = json.loads((bundle_dir / "expected" / "expected.json").read_bytes())  # never enters the process
    finished, exit_code, output = run(ws, (bundle_dir / "hidden" / "cases.json").read_bytes(), run_dir, env,
                                            limit)
    criteria.append({"criterion": "hidden_cases_finished_within_limit", "passed": finished,
                     "detail": {"limit_seconds": limit, "exit_code": exit_code}})  # exit code is evidence only
    if not finished:
        return "FAIL", criteria
    answers = None
    if output is not None and len(output) <= OUTPUT_LIMIT:
        try:
            answers = json.loads(output)
        except ValueError:
            pass
    valid = isinstance(answers, dict)
    criteria.append({"criterion": "output_file_valid", "passed": valid,
                     "detail": {"bytes": None if output is None else len(output), "limit": OUTPUT_LIMIT,
                                "digest": None if output is None else digest(output)}})
    if not valid:
        return "FAIL", criteria
    criteria.append({"criterion": "hidden_case_count_matches",
                     "passed": set(answers) == set(expected) and len(expected) == b["hidden_test_count"],
                     "detail": {"expected": b["hidden_test_count"], "returned": len(answers)}})
    failed = sorted(cid for cid, want in expected.items() if not _case_passes(answers.get(cid), want))
    criteria.append({"criterion": "hidden_cases_pass", "passed": not failed, "detail": {"failed": failed}})
    return ("PASS" if all(c["passed"] for c in criteria) else "FAIL"), criteria
