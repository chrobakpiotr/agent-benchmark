"""The single adapter between the benchmark and the agent-harness execution contract v1 (pinned v0.1.0).

Public API only (`agent_harness.contract`). There is no launch/cancel API yet (AH5-03b), so the only backend is
`fake_backend`, which answers a contract request with a contract result built from the manifest script.
A result that fails contract validation is recorded as outcome `unknown`, never as success.
"""
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agent_harness import contract

from . import __version__
from .schema import UNITS, ValidationError, canonical, digest

CANDIDATE_PATH = "candidate/output"


def utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def config_digest(config):
    return digest(canonical(config))


def build_request(manifest, config, task_digest, trial_id):
    settings = {f"{group}.{k}": v for group in ("reasoning", "sampling") for k, v in (config[group] or {}).items()}
    request = {"contract_version": contract.CONTRACT_VERSION, "request_id": f"req-{uuid.uuid4()}",
               "trial_id": trial_id, "task_digest": task_digest, "config_digest": config_digest(config),
               "provider": manifest["executor"]["kind"], "model": config["model_requested"], "settings": settings,
               "capabilities": ["usage"], "timeout_seconds": config["budget"]["max_wall_seconds"],
               "max_attempts": manifest["retry_policy"]["max_attempts"],
               "input_bindings": [{"name": "task", "sha256": task_digest}]}
    try:
        return contract.validate_request(request)
    except contract.ContractError as exc:
        raise ValidationError(f"config {config['config_id']!r} cannot be expressed as a contract request: {exc}")


def fake_backend(request, entry, candidate, evidence_root):
    """Contract v1 result for one scripted trial. Fixed codes: rejected -> BACKEND_UNAVAILABLE, error -> PROVIDER_ERROR."""
    outcome = entry["outcome"]
    result = {"contract_version": contract.CONTRACT_VERSION, "request_id": request["request_id"],
              "request_digest": contract.request_digest(request), "execution_id": None, "outcome": outcome,
              "exit_code": None, "completion": entry["completion"],
              "error_code": {"rejected": "BACKEND_UNAVAILABLE", "error": "PROVIDER_ERROR"}.get(outcome),
              "drain": None, "cancel_requested": False, "isolation_level": "fake", "resolved_model": None,
              "versions": {"agent-benchmark-fake": __version__}, "started_at": None, "ended_at": None,
              "attempts": [], "candidate": None, "artifacts": [], "usage_events": [], "usage_completeness": "unknown"}
    if outcome == "rejected":
        return result
    now = utc()
    result.update(execution_id="fake-" + request["request_id"], started_at=now, ended_at=now,
                  drain="unconfirmed" if outcome in ("timeout", "unknown") else "confirmed",
                  attempts=[{"attempt_id": "att-1", "outcome": outcome, "started_at": now, "ended_at": now}])
    if outcome == "completed":
        result["exit_code"] = 1 if entry["completion"] == "rejected" else 0
    if candidate is not None:
        path = Path(evidence_root) / CANDIDATE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(candidate)
        result["candidate"] = {"path": CANDIDATE_PATH, "sha256": digest(candidate), "size": len(candidate)}
    if entry["usage"] is not None:
        units = entry["usage"]["units"]
        result["usage_events"] = [{"contract_version": contract.CONTRACT_VERSION, "event_id": "u-1",
                                   "attempt_id": "att-1", "source": "harness", "kind": "summary", "units": units,
                                   "cache_semantics": entry["usage"]["cache_semantics"]}]
        result["usage_completeness"] = "complete" if all(units[u] is not None for u in UNITS) else "partial"
    return result


def _read_ref(evidence_root, ref):
    """Bytes behind a contract file reference, or None if missing, outside the root, or not matching size/digest."""
    root = Path(evidence_root).resolve()
    path = (root / ref["path"]).resolve()
    if root not in path.parents or not path.is_file():
        return None
    data = path.read_bytes()
    return data if len(data) == ref["size"] and digest(data) == ref["sha256"] else None


def unknown_terminal(error):
    return {"execution_id": None, "attempts": [], "outcome": "unknown", "exit_code": None, "completion": None,
            "error_code": None, "drain": None, "isolation_level": None, "resolved_model": None,
            "candidate_digest": None, "error": error}


def import_result(request, result, evidence_root, candidates_dir):
    """Validate a contract result and map it to (terminal fields, usage records). Seals a verified candidate.

    An unverifiable candidate keeps its claimed digest but is not sealed, so grading it yields INVALID.
    """
    try:
        contract.validate_result(result, request)
    except contract.ContractError as exc:
        return unknown_terminal(f"contract {exc.code}: {exc.where}"), []
    cand = result["candidate"]
    if cand is not None:
        data = _read_ref(evidence_root, cand)
        if data is not None:
            (Path(candidates_dir) / cand["sha256"].split(":", 1)[1]).write_bytes(data)
    terminal = {k: result[k] for k in ("execution_id", "outcome", "exit_code", "completion", "error_code", "drain",
                                       "isolation_level", "resolved_model")}
    terminal.update(attempts=result["attempts"], candidate_digest=cand["sha256"] if cand else None, error=None)
    usage = [{"attempt_id": e["attempt_id"], "usage_event_id": e["event_id"], "kind": e["kind"],
              "source": e["source"], "units": e["units"], "cache_semantics": e["cache_semantics"]}
             for e in result["usage_events"]]
    return terminal, usage
