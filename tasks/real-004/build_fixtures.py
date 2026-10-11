"""Builds tasks/real-004 hidden cases, expected values and task-owned evidence fixtures (run from the repo root).

Each case is a signed qualification report whose evidence lives in base/bench_fixtures/<case>/ (outside the patch
scope). The base code (agent-harness bb2cf18) signs the reports. Job ids never contain each other, so substring and
whole-token matching agree on every case.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

T = Path("tasks/real-004")
sys.path.insert(0, str(T / "base" / "src"))
from agent_harness import contract  # noqa: E402

JOB, OTHER = "nightly-build-42", "weekly-sync-7"
CASES = {  # case -> (text of each check's evidence, check whose evidence omits the job, stale review?, expected)
    "genuine": (f"raw output in job {JOB}\n", None, False, "pass"),
    "genuine_json_context": (f'{{"job": "{JOB}", "exit": 0}}\n', None, False, "pass"),
    "relabelled_job": (f"raw output in job {OTHER}\n", None, False, "raise"),
    "one_check_without_job": (f"raw output in job {JOB}\n", "Q07", False, "raise"),
    "stale_review_subject": (f"raw output in job {JOB}\n", None, True, "raise"),
}


def build(case, text, missing, stale):
    root = T / "base" / "bench_fixtures" / case
    (root / "evidence").mkdir(parents=True)

    def evidence(name, body):
        path = root / "evidence" / f"{name}.log"
        path.write_text(body)
        data = path.read_bytes()
        return {"path": f"evidence/{name}.log", "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
                "size": len(data)}

    doc = {"contract_version": 1, "target": "bench-target", "policy_digest": "sha256:" + "2" * 64,
           "author": "qualifier",
           "tuple": {"job_id": JOB, "host": "ubuntu-24.04", "kernel": "6.8.0", "engine": "docker-29.8.2",
                     "workload_image": "sha256:" + "3" * 64},
           "checks": [{"id": i, "result": "pass",
                       "evidence": [evidence(i, f"check {i}: " + ("raw output, exit 0\n" if i == missing else text))]}
                      for i in contract.QUALIFICATION_CHECKS],
           "independent_review": None, "created_at": "2026-10-06T00:00:00Z"}
    subject = contract.review_subject(doc)
    named = "sha256:" + "a" * 64 if stale else subject
    doc["independent_review"] = {"reviewer": "security-reviewer", "subject": subject, "verdict": "pass",
                                 "evidence": evidence("review", f"review of {named}: pass\n")}
    contract.validate_qualification_report(doc)
    return doc


shutil.rmtree(T / "base" / "bench_fixtures", ignore_errors=True)
cases, expected = [], {}
for case, (text, missing, stale, want) in CASES.items():
    cases.append({"id": case, "function": "qualification_passes",
                  "args": [build(case, text, missing, stale), f"bench_fixtures/{case}"]})
    expected[case] = {"raises": "ContractError"} if want == "raise" else {"value": True}
(T / "hidden" / "cases.json").write_text(
    json.dumps({"module": "src.agent_harness.contract", "cases": cases}, indent=1) + "\n")
(T / "expected" / "expected.json").write_text(json.dumps(expected, indent=1) + "\n")
print(len(cases), "cases")
