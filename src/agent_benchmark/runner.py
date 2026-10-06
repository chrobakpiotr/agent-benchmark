"""Sequential runner: validate -> plan trials -> contract request -> backend -> import result -> grade -> events.

Execution goes through `harness_port` (agent-harness launch API, contract v1). The only backend is the harness
ScriptedBackend (fake); every record says so.

Crash safety: `trial_started` is written before launch, so a missing start means the trial was never launched.
A start without a terminal is never silently re-run; `resume` reconciles it to `unknown` first.
"""
import json
import os
import random
import shutil
import time
import uuid
from pathlib import Path

from . import grader, harness_port
from .report import load_run, reduce_events
from .schema import EVENT_VERSION, FAKE_TRACK, ValidationError, canonical, digest, load_manifest


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


def fake_candidate(task, bundle_dir, kind):
    if task["grader"]["id"] != "sort-check":
        return (Path(bundle_dir) / "reference" / f"{kind}.patch").read_bytes()
    data = task["input"]
    return {
        "good": lambda: canonical(sorted(data)),
        "wrong": lambda: canonical(sorted(data, reverse=True)),
        "noop": lambda: canonical(data),
        "malformed": lambda: b"not json",
    }[kind]()


def fake_execute(request, task, entry, bundle_dir, evidence_root):
    """Fake backend: answers a contract request with the scripted outcome. No model, no network."""
    candidate = fake_candidate(task, bundle_dir, entry["candidate"]) if entry["candidate"] else None
    return harness_port.launch(request, harness_port.scripted_backend(entry, candidate), evidence_root)


def _utc():
    return harness_port.utc()


def _append(path, record):
    """Append-only, one fsync'ed JSON line per event, each with its own event_id."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"schema_version": EVENT_VERSION, "event_id": str(uuid.uuid4()), **record},
                           sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _grade(out, manifest, task, trial_id, cand_digest):
    # Candidate code may run on the host only when it comes from the fake executor's reference set.
    result, criteria = grader.grade(task, out / "candidates", cand_digest, bundle_dir=out / "task",
                                    host_execution_allowed=manifest["executor"]["kind"] == "fake")
    gid = task["grader"]["id"]
    _append(out / "events.jsonl", {"type": "grade", "trial_id": trial_id, "candidate_digest": cand_digest,
                                   "grader": grader.identity(gid), "result": result, "criteria": criteria,
                                   "isolation": grader.ISOLATION[gid]})


def _execute(out, manifest, task, task_digest, todo, execute):
    """todo: [(config_id, repetition, trial_id, replaces)] executed sequentially."""
    events = out / "events.jsonl"
    script = {(e["config_id"], e["repetition"]): e for e in manifest["executor"]["script"]}
    configs = {c["config_id"]: c for c in manifest["configs"]}
    for cid, rep, trial_id, replaces in todo:
        request = harness_port.build_request(manifest, configs[cid], task_digest, trial_id)
        evidence = out / "evidence" / request["request_id"]
        evidence.mkdir(parents=True)
        (evidence / "request.json").write_bytes(canonical(request))
        _append(events, {"type": "trial_started", "trial_id": trial_id, "config_id": cid, "repetition": rep,
                         "request_id": request["request_id"], "request_digest": digest(canonical(request)),
                         "replaces": replaces, "started_utc": _utc()})
        t0 = time.monotonic_ns()
        try:
            result = execute(request, task, script[(cid, rep)], out / "task", evidence)
        except Exception as exc:  # backend crashed: launch state unknown, the trial stays visible
            terminal, usage = harness_port.unknown_terminal(f"backend raised {type(exc).__name__}"), []
        else:
            (evidence / "result.json").write_bytes(canonical(result))  # raw, even if it fails validation
            terminal, usage = harness_port.import_result(request, result, evidence, out / "candidates")
        duration_ms = (time.monotonic_ns() - t0) // 1_000_000
        _append(events, {"type": "trial_finished", "trial_id": trial_id, "request_id": request["request_id"],
                         "source": "executor", **terminal, "finished_utc": _utc(), "duration_ms": duration_ms})
        for u in usage:
            _append(events, {"type": "usage", "trial_id": trial_id, **u})
        if terminal["candidate_digest"]:
            _grade(out, manifest, task, trial_id, terminal["candidate_digest"])


def run(manifest_path, out_dir, execute=fake_execute):
    manifest, task, manifest_bytes, task_bytes = load_manifest(manifest_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)  # never overwrite an earlier run's records
    (out / "manifest.json").write_bytes(manifest_bytes)
    task_dir = Path(manifest_path).parent / manifest["task"]["path"]
    shutil.copytree(task_dir.parent, out / "task", ignore=shutil.ignore_patterns("__pycache__"))
    (out / "candidates").mkdir()
    plan = plan_trials(manifest)
    run_id = str(uuid.uuid4())
    _append(out / "events.jsonl", {"type": "run_started", "run_id": run_id, "experiment_id": manifest["experiment_id"],
                                   "manifest_digest": digest(manifest_bytes), "task_digest": digest(task_bytes),
                                   "executor": {"kind": "fake", "track": FAKE_TRACK},
                                   "plan": [f"{c}/r{r}" for c, r in plan]})
    _execute(out, manifest, task, digest(task_bytes), [(c, r, f"{c}/r{r}", None) for c, r in plan], execute)
    _append(out / "events.jsonl", {"type": "run_finished", "run_id": run_id, "finished_utc": _utc()})
    return out


def resume(run_dir, replace_unknown=False, execute=fake_execute):
    """Continue an interrupted run without re-running anything that may already have been launched.

    - started but no terminal -> reconciled to outcome 'unknown' (stays visible, counts in the denominator);
      with replace_unknown a replacement trial gets a new identity linked via `replaces`
    - terminal with a sealed candidate but no grade -> graded now (offline, deterministic)
    - planned but never started -> executed
    """
    out = Path(run_dir)
    manifest, task, events, _ = load_run(out)
    rows = {r["trial_id"]: r for r in reduce_events(events)["trials"]}
    plan = plan_trials(manifest)
    if [f"{c}/r{r}" for c, r in plan] != events[0]["plan"]:
        raise ValidationError("events.jsonl: recorded plan does not match the manifest plan")
    interrupted = [r for r in rows.values() if r["interrupted"]]
    ungraded = [r for r in rows.values() if r["candidate_digest"] and r["original_grade"] is None]
    todo = [(c, r, f"{c}/r{r}", None) for c, r in plan if f"{c}/r{r}" not in rows]
    if replace_unknown:
        for r in interrupted:
            n = sum(1 for x in rows.values() if x["trial_id"].startswith(r["trial_id"] + "/x")) + 1
            todo.append((r["config_id"], r["repetition"], f"{r['trial_id']}/x{n}", r["trial_id"]))
    if not (interrupted or ungraded or todo):
        raise ValidationError(f"{out}: nothing to resume")

    events_path = out / "events.jsonl"
    run_id = events[0]["run_id"]
    _append(events_path, {"type": "run_resumed", "run_id": run_id, "resumed_utc": _utc()})
    for r in interrupted:
        _append(events_path, {"type": "trial_finished", "trial_id": r["trial_id"], "request_id": r["request_id"],
                              "source": "reconciliation", **harness_port.unknown_terminal(
                                  "interrupted between launch and terminal record; no backend status available"),
                              "finished_utc": _utc(), "duration_ms": None})
    for r in ungraded:
        _grade(out, manifest, task, r["trial_id"], r["candidate_digest"])
    _execute(out, manifest, task, events[0]["task_digest"], todo, execute)
    _append(events_path, {"type": "run_finished", "run_id": run_id, "finished_utc": _utc()})
    return out


def invalidate(run_dir, trial_id, reason):
    """Append a correction record. The original grade stays in history; the effective grade becomes INVALID."""
    out = Path(run_dir)
    _, _, events, _ = load_run(out)
    if trial_id not in {r["trial_id"] for r in reduce_events(events)["trials"]}:
        raise ValidationError(f"unknown trial {trial_id!r}")
    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError("a correction needs a non-empty reason")
    _append(out / "events.jsonl", {"type": "correction", "trial_id": trial_id, "action": "invalidate",
                                   "reason": reason, "created_utc": _utc()})
