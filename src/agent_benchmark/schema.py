"""Manifest, task bundle and event record validation. Rejects instead of guessing; unknown stays null."""
import hashlib
import json
from pathlib import Path

MANIFEST_VERSION = "agent-benchmark/manifest/v1"
TASK_VERSION = "agent-benchmark/task/v1"
EVENT_VERSION = "agent-benchmark/event/v2"

OUTCOMES = ("completed", "timeout", "cancel", "error", "unknown")
EXCLUDABLE_OUTCOMES = OUTCOMES[1:]  # predeclared infrastructure exclusions; "completed" never
HARNESS_COMPLETION = ("success", "failure")
GRADES = ("PASS", "FAIL", "INVALID")
QUALITY = ("complete", "partial", "unknown")
FAKE_CANDIDATES = ("good", "wrong", "noop", "malformed")
FAKE_TRACK = "fake-offline"
KNOWN_GRADERS = {"sort-check": "1"}
USAGE_FIELDS = ("input_tokens", "output_tokens", "cache_read_tokens")

CONFIG_REQUIRED = ("config_id", "model_requested", "workflow", "tool_permissions", "isolation_track")
CONFIG_NULLABLE = ("model_resolved", "cli", "cli_version", "prompt_digest", "reasoning", "sampling", "budget")

EVENT_FIELDS = {
    "run_started": ("run_id", "experiment_id", "manifest_digest", "task_digest", "executor", "plan"),
    "run_resumed": ("run_id", "resumed_utc"),
    "trial_started": ("trial_id", "config_id", "repetition", "request_id", "replaces", "started_utc"),
    "trial_finished": ("trial_id", "request_id", "source", "execution_id", "attempts", "outcome",
                       "harness_completion", "candidate_digest", "finished_utc", "duration_ms", "error"),
    "usage": ("trial_id", "attempt_id", "usage_event_id", "kind", "usage"),
    "grade": ("trial_id", "candidate_digest", "grader", "result", "criteria", "isolation"),
    "correction": ("trial_id", "action", "reason", "created_utc"),
    "run_finished": ("run_id", "finished_utc"),
}
TERMINAL_SOURCES = ("executor", "reconciliation")
USAGE_KINDS = ("stream", "summary")
CORRECTION_ACTIONS = ("invalidate",)  # corrections can only lower a result, never turn a failure into PASS


class ValidationError(ValueError):
    pass


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _fail(path, msg):
    raise ValidationError(f"{path}: {msg}")


def _keys(obj, path, required, nullable=()):
    if not isinstance(obj, dict):
        _fail(path, "must be an object")
    allowed = set(required) | set(nullable)
    missing = [k for k in (*required, *nullable) if k not in obj]
    if missing:
        _fail(path, f"missing fields {missing} (unknown values must be explicit null)")
    extra = sorted(set(obj) - allowed)
    if extra:
        _fail(path, f"unknown fields {extra}")


def _str(v, path, nullable=False):
    if v is None and nullable:
        return
    if not isinstance(v, str) or not v.strip():
        _fail(path, "must be a non-empty string" + (" or null" if nullable else ""))


def _int(v, path, lo, hi=None, nullable=False):
    if v is None and nullable:
        return
    if isinstance(v, bool) or not isinstance(v, int) or v < lo or (hi is not None and v > hi):
        _fail(path, f"must be an integer in [{lo}, {hi if hi is not None else 'inf'}]" + (" or null" if nullable else ""))


def _enum(v, path, values, nullable=False):
    if v is None and nullable:
        return
    if v not in values:
        _fail(path, f"must be one of {list(values)}" + (" or null" if nullable else "") + f", got {v!r}")


def _version(obj, path, expected):
    if not isinstance(obj, dict):
        _fail(path, "must be an object")
    if obj.get("schema_version") != expected:
        _fail(f"{path}.schema_version", f"unsupported {obj.get('schema_version')!r}, expected {expected!r}")


def validate_usage(u, path):
    """null = unknown usage (valid). complete = every field known; partial = at least one known."""
    if u is None:
        return
    _keys(u, path, ("source", "completeness", *USAGE_FIELDS))
    _str(u["source"], f"{path}.source")
    _enum(u["completeness"], f"{path}.completeness", ("complete", "partial"))
    for f in USAGE_FIELDS:
        _int(u[f], f"{path}.{f}", 0, nullable=True)
    known = [u[f] is not None for f in USAGE_FIELDS]
    if u["completeness"] == "complete" and not all(known):
        _fail(path, "completeness 'complete' contradicts null fields")
    if u["completeness"] == "partial" and (all(known) or not any(known)):
        _fail(path, "completeness 'partial' requires some but not all fields known")


def validate_task(task):
    _version(task, "task", TASK_VERSION)
    _keys(task, "task", ("schema_version", "task_id", "version", "description", "environment", "visible_checks",
                         "input", "grader", "provenance", "license"))
    for f in ("task_id", "version", "description", "environment", "provenance", "license"):
        _str(task[f], f"task.{f}")
    if not isinstance(task["visible_checks"], list) or not all(isinstance(c, str) for c in task["visible_checks"]):
        _fail("task.visible_checks", "must be a list of strings")
    if not isinstance(task["input"], list) or not task["input"]:
        _fail("task.input", "must be a non-empty list")
    for i, v in enumerate(task["input"]):
        _int(v, f"task.input[{i}]", -2**53)
    _keys(task["grader"], "task.grader", ("id", "version"))
    gid, gver = task["grader"]["id"], task["grader"]["version"]
    if KNOWN_GRADERS.get(gid) != gver:
        _fail("task.grader", f"unknown grader {gid!r} version {gver!r}; known {KNOWN_GRADERS}")
    return task


def validate_config(c, path):
    _keys(c, path, CONFIG_REQUIRED, CONFIG_NULLABLE)
    for f in ("config_id", "model_requested", "workflow", "isolation_track"):
        _str(c[f], f"{path}.{f}")
    for f in ("model_resolved", "cli", "cli_version", "prompt_digest"):
        _str(c[f], f"{path}.{f}", nullable=True)
    for f in ("reasoning", "sampling"):
        if c[f] is not None and not isinstance(c[f], dict):
            _fail(f"{path}.{f}", "must be an object or null")
    if not isinstance(c["tool_permissions"], list) or not all(isinstance(t, str) for t in c["tool_permissions"]):
        _fail(f"{path}.tool_permissions", "must be a list of strings")
    if c["budget"] is not None:
        _keys(c["budget"], f"{path}.budget", (), ("max_wall_seconds",))
        _int(c["budget"]["max_wall_seconds"], f"{path}.budget.max_wall_seconds", 1, nullable=True)


def validate_manifest(m, task_digest=None):
    """Validate an experiment manifest; with task_digest also check the task binding."""
    _version(m, "manifest", MANIFEST_VERSION)
    _keys(m, "manifest", ("schema_version", "experiment_id", "task", "configs", "repetitions", "seed",
                          "retry_policy", "exclusions", "executor"))
    _str(m["experiment_id"], "manifest.experiment_id")
    _keys(m["task"], "manifest.task", ("path", "digest"))
    _str(m["task"]["path"], "manifest.task.path")
    _str(m["task"]["digest"], "manifest.task.digest")
    if task_digest is not None and m["task"]["digest"] != task_digest:
        _fail("manifest.task.digest", f"binding mismatch: manifest {m['task']['digest']}, bundle {task_digest}")
    _int(m["repetitions"], "manifest.repetitions", 1, 1000)
    _int(m["seed"], "manifest.seed", 0)
    _keys(m["retry_policy"], "manifest.retry_policy", ("max_attempts",))
    _int(m["retry_policy"]["max_attempts"], "manifest.retry_policy.max_attempts", 1, 1)  # retries: AB5-03/06
    if not isinstance(m["exclusions"], list):
        _fail("manifest.exclusions", "must be a list")
    for i, x in enumerate(m["exclusions"]):
        _keys(x, f"manifest.exclusions[{i}]", ("outcome", "reason"))
        _enum(x["outcome"], f"manifest.exclusions[{i}].outcome", EXCLUDABLE_OUTCOMES)
        _str(x["reason"], f"manifest.exclusions[{i}].reason")
    if len({x["outcome"] for x in m["exclusions"]}) != len(m["exclusions"]):
        _fail("manifest.exclusions", "duplicate outcome")

    if not isinstance(m["configs"], list) or not m["configs"]:
        _fail("manifest.configs", "must be a non-empty list")
    ids = []
    for i, c in enumerate(m["configs"]):
        validate_config(c, f"manifest.configs[{i}]")
        ids.append(c["config_id"])
    if len(set(ids)) != len(ids):
        _fail("manifest.configs", f"duplicate config_id in {ids}")

    ex = m["executor"]
    _keys(ex, "manifest.executor", ("kind", "script"))
    _enum(ex["kind"], "manifest.executor.kind", ("fake",))
    for i, c in enumerate(m["configs"]):
        if c["isolation_track"] != FAKE_TRACK:
            _fail(f"manifest.configs[{i}].isolation_track", f"fake executor requires {FAKE_TRACK!r}")
    if not isinstance(ex["script"], list):
        _fail("manifest.executor.script", "must be a list")
    seen = set()
    for i, e in enumerate(ex["script"]):
        p = f"manifest.executor.script[{i}]"
        _keys(e, p, ("config_id", "repetition", "outcome", "candidate", "harness_completion", "usage"))
        if e["config_id"] not in ids:
            _fail(f"{p}.config_id", f"binding to unknown config {e['config_id']!r}")
        _int(e["repetition"], f"{p}.repetition", 1, m["repetitions"])
        _enum(e["outcome"], f"{p}.outcome", OUTCOMES)
        _enum(e["candidate"], f"{p}.candidate", FAKE_CANDIDATES, nullable=True)
        _enum(e["harness_completion"], f"{p}.harness_completion", HARNESS_COMPLETION, nullable=True)
        validate_usage(e["usage"], f"{p}.usage")
        if e["outcome"] == "completed" and e["candidate"] is None:
            _fail(p, "outcome 'completed' without a candidate")
        key = (e["config_id"], e["repetition"])
        if key in seen:
            _fail(p, f"duplicate script entry for {key}")
        seen.add(key)
    missing = [(c, r) for c in ids for r in range(1, m["repetitions"] + 1) if (c, r) not in seen]
    if missing:
        _fail("manifest.executor.script", f"no scripted outcome for planned trials {missing}")
    return m


def load_manifest(path):
    """Load + validate manifest and its bound task bundle. Returns (manifest, task, manifest_bytes, task_bytes)."""
    path = Path(path)
    manifest_bytes = path.read_bytes()
    m = _json(manifest_bytes, str(path))
    _version(m, "manifest", MANIFEST_VERSION)
    task_path = path.parent / m.get("task", {}).get("path", "")
    if not task_path.is_file():
        _fail("manifest.task.path", f"task bundle not found: {task_path}")
    task_bytes = task_path.read_bytes()
    validate_manifest(m, digest(task_bytes))
    return m, validate_task(_json(task_bytes, str(task_path))), manifest_bytes, task_bytes


def validate_event(e, path):
    _version(e, path, EVENT_VERSION)
    if e.get("type") not in EVENT_FIELDS:
        _fail(f"{path}.type", f"unknown event type {e.get('type')!r}")
    _keys(e, path, ("schema_version", "type", "event_id", *EVENT_FIELDS[e["type"]]))
    _str(e["event_id"], f"{path}.event_id")
    if e["type"] == "trial_finished":
        _enum(e["source"], f"{path}.source", TERMINAL_SOURCES)
        _enum(e["outcome"], f"{path}.outcome", OUTCOMES)
        _enum(e["harness_completion"], f"{path}.harness_completion", HARNESS_COMPLETION, nullable=True)
        if not isinstance(e["attempts"], list):
            _fail(f"{path}.attempts", "must be a list")
        for i, a in enumerate(e["attempts"]):
            _keys(a, f"{path}.attempts[{i}]", ("attempt_id", "outcome"))
            _str(a["attempt_id"], f"{path}.attempts[{i}].attempt_id")
    if e["type"] == "usage":
        _str(e["attempt_id"], f"{path}.attempt_id")
        _str(e["usage_event_id"], f"{path}.usage_event_id")
        _enum(e["kind"], f"{path}.kind", USAGE_KINDS)
        if e["usage"] is None:
            _fail(f"{path}.usage", "a usage event must carry usage; unknown usage is the absence of events")
        validate_usage(e["usage"], f"{path}.usage")
    if e["type"] == "grade":
        _enum(e["result"], f"{path}.result", GRADES)
    if e["type"] == "correction":
        _enum(e["action"], f"{path}.action", CORRECTION_ACTIONS)
        _str(e["reason"], f"{path}.reason")
    return e


def _json(data, where):
    try:
        return json.loads(data)
    except ValueError as exc:
        raise ValidationError(f"{where}: invalid JSON: {exc}") from None
