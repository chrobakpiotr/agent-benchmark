"""The single adapter between the benchmark and agent-harness (contract v2 + offline launch API, pinned v0.6.1).

Public API only (`agent_harness.contract`, `agent_harness.execution`). The harness launches every trial and seals
its candidate into the trial's evidence root; the only backend the runner uses is the harness `ScriptedBackend`
built from the manifest script (`isolation_level: fake`). A result that fails contract validation is recorded as
outcome `unknown`, never as success.
"""
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agent_harness import contract, execution

from .schema import ValidationError, canonical, digest

# Fixed codes for scripted outcomes; a scripted `rejected` means the backend was unavailable (never launched).
SCRIPTED_ERROR, SCRIPTED_REJECTION = "PROVIDER_ERROR", "BACKEND_UNAVAILABLE"


def utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def config_digest(config):
    return digest(canonical(config))


def build_request(manifest, config, task_digest, trial_id, capabilities=("usage",), limits=None):
    settings = {f"{group}.{k}": v for group in ("reasoning", "sampling") for k, v in (config[group] or {}).items()}
    request = {"contract_version": 2, "request_id": f"req-{uuid.uuid4()}",
               "trial_id": trial_id, "task_digest": task_digest, "config_digest": config_digest(config),
               "provider": config["cli"] or manifest["executor"]["kind"], "model": config["model_requested"], "settings": settings,
               "capabilities": list(capabilities), "timeout_seconds": config["budget"]["max_wall_seconds"],
               "max_attempts": manifest["retry_policy"]["max_attempts"],
               "input_bindings": [{"name": "task", "sha256": task_digest}], "limits": limits}
    try:
        return contract.validate_request(request)
    except contract.ContractError as exc:
        raise ValidationError(f"config {config['config_id']!r} cannot be expressed as a contract request: {exc}")


def scripted_backend(entry, candidate):
    """Harness ScriptedBackend answering one manifest script entry (one attempt)."""
    if entry["outcome"] == "rejected":
        return execution.ScriptedBackend(rejection=SCRIPTED_REJECTION)
    usage = entry["usage"]
    return execution.ScriptedBackend([{"outcome": entry["outcome"], "units": usage["units"] if usage else None}],
                                     exit_code=1 if entry["completion"] == "rejected" else 0,
                                     completion=entry["completion"], error_code=SCRIPTED_ERROR, candidate=candidate,
                                     cache_semantics=usage["cache_semantics"] if usage else "separate")


def launch(request, backend, evidence_root, workspace=None):
    """Launch through the harness and wait for the terminal result; without a workspace the evidence root is used.
    No result within the request timeout + 60 s: the execution is cancelled and TimeoutError raised, so the caller
    records `unknown`."""
    root = str(Path(evidence_root).resolve())
    handle = execution.launch(request, backend, workspace=str(Path(workspace).resolve()) if workspace else root,
                              evidence_root=root)
    try:
        return handle.result(request["timeout_seconds"] + 60)
    except TimeoutError:
        handle.cancel()
        raise


def agent_prompt(task):
    """What the agent is told: the task text and its visible checks, nothing from the hidden material."""
    checks = "\n".join(f"- {c}" for c in task["visible_checks"])
    return (f"{task['description']}\n\nVisible checks you may run:\n{checks}\n\n"
            "Work only in the current directory. Edit the files in place; do not commit.\n")


def prepare_workspace(base_dir, workspace):
    """Copy the task's base tree into a fresh Git repository with one base commit; return the commit id."""
    shutil.copytree(base_dir, workspace)
    env = {"PATH": os.defpath, "HOME": str(workspace), "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_AUTHOR_NAME": "agent-benchmark", "GIT_AUTHOR_EMAIL": "base@agent-benchmark",
           "GIT_COMMITTER_NAME": "agent-benchmark", "GIT_COMMITTER_EMAIL": "base@agent-benchmark",
           "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}
    for argv in (["init", "-q"], ["add", "-A"], ["commit", "-q", "--no-verify", "-m", "base"]):
        subprocess.run(["git", *argv], cwd=workspace, env=env, check=True, capture_output=True)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=workspace, env=env, check=True, capture_output=True,
                          text=True).stdout.strip()


def agent_cli_backend(config, task, diff_base):
    """Harness AgentCliBackend for one config: the CLI's own login and sandbox, candidate = workspace diff."""
    return execution.AgentCliBackend(config["cli"], agent_prompt(task), diff_base=diff_base)


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
            "candidate_digest": None, "error": error, "target": None, "limits": None}


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
    terminal.update(attempts=result["attempts"], candidate_digest=cand["sha256"] if cand else None, error=None,
                    target=result.get("target"), limits=result.get("limits"))  # v2 only; null on v1 results
    usage = [{"attempt_id": e["attempt_id"], "usage_event_id": e["event_id"], "kind": e["kind"],
              "source": e["source"], "units": e["units"], "cache_semantics": e["cache_semantics"]}
             for e in result["usage_events"]]
    return terminal, usage
