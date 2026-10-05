"""Sequential runner: validate -> plan trials -> execute (fake port) -> seal candidate -> grade -> append events.

The execution port (see docs/execution-port.md) is owned by agent-harness AH5-02. `fake_execute` is the only
implementation here and is labelled fake in every record.
"""
import json
import os
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import grader
from .schema import EVENT_VERSION, FAKE_TRACK, canonical, digest, load_manifest


def plan_trials(manifest):
    """Balanced order: every repetition block contains each config once; order inside a block is seeded."""
    rng = random.Random(manifest["seed"])
    ids = [c["config_id"] for c in manifest["configs"]]
    order = []
    for rep in range(1, manifest["repetitions"] + 1):
        block = ids[:]
        rng.shuffle(block)
        order += [(cid, rep) for cid in block]
    return order


def fake_execute(request, task, entry):
    """Fake execution port: returns the scripted outcome. No model, no network, no code execution."""
    data = task["input"]
    candidate = {
        "good": lambda: canonical(sorted(data)),
        "wrong": lambda: canonical(sorted(data, reverse=True)),
        "noop": lambda: canonical(data),
        "malformed": lambda: b"not json",
    }[entry["candidate"]]() if entry["candidate"] else None
    execution_id = "fake-exec-" + request["request_id"]
    return {
        "execution_id": execution_id,
        "attempts": [{"attempt_id": execution_id + "-a1", "outcome": entry["outcome"]}],
        "outcome": entry["outcome"],
        "harness_completion": entry["harness_completion"],
        "candidate": candidate,
        "usage": entry["usage"],
    }


def _utc():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _append(path, record):
    """Append-only, one fsync'ed JSON line per event."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"schema_version": EVENT_VERSION, **record}, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def run(manifest_path, out_dir, execute=fake_execute):
    manifest, task, manifest_bytes, task_bytes = load_manifest(manifest_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)  # never overwrite an earlier run's records
    (out / "manifest.json").write_bytes(manifest_bytes)
    (out / "task.json").write_bytes(task_bytes)
    candidates = out / "candidates"
    candidates.mkdir()
    events = out / "events.jsonl"
    script = {(e["config_id"], e["repetition"]): e for e in manifest["executor"]["script"]}
    plan = plan_trials(manifest)
    run_id = str(uuid.uuid4())

    _append(events, {"type": "run_started", "run_id": run_id, "experiment_id": manifest["experiment_id"],
                     "manifest_digest": digest(manifest_bytes), "task_digest": digest(task_bytes),
                     "executor": {"kind": "fake", "track": FAKE_TRACK},
                     "plan": [f"{c}/r{r}" for c, r in plan]})
    for cid, rep in plan:
        trial_id = f"{cid}/r{rep}"
        request = {"request_id": str(uuid.uuid4()), "trial_id": trial_id, "config_id": cid}
        _append(events, {"type": "trial_started", "trial_id": trial_id, "config_id": cid, "repetition": rep,
                         "request_id": request["request_id"], "started_utc": _utc()})
        t0 = time.monotonic_ns()
        try:
            result = execute(request, task, script[(cid, rep)])
        except Exception as exc:  # an executor crash is a recorded outcome, not a lost trial
            result = {"execution_id": None, "attempts": [], "outcome": "error", "harness_completion": None,
                      "candidate": None, "usage": None, "error": f"{type(exc).__name__}: {exc}"}
        duration_ms = (time.monotonic_ns() - t0) // 1_000_000
        cand = result["candidate"]
        cand_digest = None
        if cand is not None:
            cand_digest = digest(cand)
            (candidates / cand_digest.split(":", 1)[1]).write_bytes(cand)  # seal: content-addressed
        usage = result["usage"]
        _append(events, {"type": "trial_finished", "trial_id": trial_id, "request_id": request["request_id"],
                         "execution_id": result["execution_id"], "attempts": result["attempts"],
                         "outcome": result["outcome"], "harness_completion": result["harness_completion"],
                         "candidate_digest": cand_digest, "usage": usage,
                         "measurement_quality": usage["completeness"] if usage else "unknown",
                         "finished_utc": _utc(), "duration_ms": duration_ms,
                         "error": result.get("error")})
        if cand_digest:
            result_grade, criteria = grader.grade(task, candidates, cand_digest)
            _append(events, {"type": "grade", "trial_id": trial_id, "candidate_digest": cand_digest,
                             "grader": grader.identity(), "result": result_grade, "criteria": criteria,
                             "isolation": grader.ISOLATION})
    _append(events, {"type": "run_finished", "run_id": run_id, "finished_utc": _utc()})
    return out
