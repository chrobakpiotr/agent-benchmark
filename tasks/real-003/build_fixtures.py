"""Builds tasks/real-003 hidden cases, expected values and task-owned evidence fixtures (run from the repo root).

Each case is a qualification report whose evidence files live in base/bench_fixtures/<case>/ (outside the patch
scope) and name the job in one textual context. The base code (agent-harness 9e01ec4) is imported to sign the report.
"""
import copy, hashlib, json, shutil, sys
from pathlib import Path

T = Path("tasks/real-003")
sys.path.insert(0, str(T / "base" / "src"))
from agent_harness import contract  # noqa: E402

JOB = "nightly-run-7-attempt-1"
CASES = {  # case id -> (text naming the job, expected)
    "suffix_digit": (f"raw output in job {JOB}0\n", "raise"),
    "suffix_letter": (f"raw output in job {JOB}b\n", "raise"),
    "prefix_word": (f"raw output in job re{JOB}\n", "raise"),
    "suffix_hyphen_word": (f"raw output in job {JOB}-retry\n", "raise"),
    "own_job_line_end": (f"raw output in job {JOB}\n", "pass"),
    "own_job_quoted": (f'{{"job": "{JOB}", "exit": 0}}\n', "pass"),
    "own_job_parenthesised": (f"raw output (job {JOB}) done\n", "pass"),
}


def build(case, text):
    root = T / "base" / "bench_fixtures" / case
    (root / "evidence").mkdir(parents=True)

    def evidence(name, body):
        path = root / "evidence" / f"{name}.log"
        path.write_text(body)
        data = path.read_bytes()
        return {"path": f"evidence/{name}.log", "sha256": "sha256:" + hashlib.sha256(data).hexdigest(), "size": len(data)}
    doc = {"contract_version": 1, "target": "bench-target", "policy_digest": "sha256:" + "2" * 64, "author": "qualifier",
           "tuple": {"job_id": JOB, "host": "ubuntu-24.04", "kernel": "6.8.0", "engine": "docker-29.8.2",
                     "workload_image": "sha256:" + "3" * 64},
           "checks": [{"id": i, "result": "pass", "evidence": [evidence(i, f"check {i}: " + text)]}
                      for i in contract.QUALIFICATION_CHECKS],
           "independent_review": None, "created_at": "2026-10-06T00:00:00Z"}
    subject = contract.review_subject(doc)
    doc["independent_review"] = {"reviewer": "security-reviewer", "subject": subject, "verdict": "pass",
                                 "evidence": evidence("review", f"review of {subject}: pass\n")}
    contract.validate_qualification_report(doc)
    return doc


shutil.rmtree(T / "base" / "bench_fixtures", ignore_errors=True)
cases, expected = [], {}
for case, (text, want) in CASES.items():
    cases.append({"id": case, "function": "qualification_passes", "args": [build(case, text), f"bench_fixtures/{case}"]})
    expected[case] = {"raises": "ContractError"} if want == "raise" else {"value": True}
(T / "hidden" / "cases.json").write_text(json.dumps({"module": "src.agent_harness.contract", "cases": cases}, indent=1) + "\n")
(T / "expected" / "expected.json").write_text(json.dumps(expected, indent=1) + "\n")
print(len(cases), "cases")
