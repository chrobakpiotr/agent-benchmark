"""Manifest, task bundle and event record validation. Rejects instead of guessing; unknown stays null."""
import hashlib
import json
import re
from pathlib import Path

from agent_harness.contract import ERROR_CODES, FIRED_LIMITS, LIMIT_EXCEEDED, OUTCOMES

MANIFEST_VERSION = "agent-benchmark/manifest/v2"
TASK_VERSION = "agent-benchmark/task/v1"
EVENT_VERSION = "agent-benchmark/event/v4"

# Execution vocabulary comes from the agent-harness execution contract (v2); only what it does not export is here.
EXCLUDABLE_OUTCOMES = tuple(o for o in OUTCOMES if o != "completed")  # predeclared exclusions; "completed" never
COMPLETION = ("accepted", "rejected")
CACHE_SEMANTICS = ("separate", "included_in_input", "unknown")  # contract v1 usage event enum (not exported)
UNITS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")
CONFIG_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}")  # becomes part of contract trial_id; no "/"
GRADES = ("PASS", "FAIL", "INVALID")
QUALITY = ("complete", "partial", "unknown")
FAKE_CANDIDATES = ("good", "wrong", "noop", "malformed")
FAKE_TRACK = "fake-offline"
CONTROLLED_TRACK = "controlled-host"  # agent CLI on this host in its own sandbox (harness AgentCliBackend)
AGENT_CLIS = ("claude", "codex")
KNOWN_GRADERS = {"sort-check": "1", "patch-unittest": "1", "patch-io": "1"}

CONFIG_REQUIRED = ("config_id", "model_requested", "workflow", "tool_permissions", "isolation_track", "budget")
CONFIG_NULLABLE = ("model_resolved", "cli", "cli_version", "prompt_digest", "reasoning", "sampling")

EVENT_FIELDS = {
    "run_started": ("run_id", "experiment_id", "manifest_digest", "task_digest", "executor", "plan"),
    "run_resumed": ("run_id", "resumed_utc"),
    "trial_started": ("trial_id", "config_id", "repetition", "request_id", "request_digest", "replaces",
                      "started_utc"),
    "trial_finished": ("trial_id", "request_id", "source", "execution_id", "attempts", "outcome", "exit_code",
                       "completion", "error_code", "drain", "isolation_level", "resolved_model",
                       "candidate_digest", "finished_utc", "duration_ms", "error", "target", "limits"),
    "usage": ("trial_id", "attempt_id", "usage_event_id", "kind", "source", "units", "cache_semantics"),
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


def validate_units(units, path):
    """Contract v1 usage units: every unit present, each a non-negative integer or null (unknown)."""
    _keys(units, path, (), UNITS)
    for f in UNITS:
        _int(units[f], f"{path}.{f}", 0, nullable=True)


def tree_digest(root):
    """Digest of a directory: sorted relative paths with per-file digests. Symlinks are refused."""
    root = Path(root)
    lines = []
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            _fail(str(p), "symlinks are not allowed in a task bundle")
        if p.is_file() and "__pycache__" not in p.parts:
            lines.append(f"{p.relative_to(root).as_posix()} {digest(p.read_bytes())}\n")
    return digest("".join(lines).encode())


TASK_COMMON = ("schema_version", "task_id", "version", "description", "environment", "visible_checks", "grader",
               "provenance", "license")
TASK_SPECIFIC = {"sort-check": ("input",), "patch-unittest": ("bundle",), "patch-io": ("bundle",)}
# patch-io keeps expected values in their own tree, never copied next to the candidate
BUNDLE_TREES = {"patch-unittest": ("base", "hidden"), "patch-io": ("base", "hidden", "expected")}


def validate_task(task):
    _version(task, "task", TASK_VERSION)
    _keys(task.get("grader"), "task.grader", ("id", "version"))
    gid, gver = task["grader"]["id"], task["grader"]["version"]
    if KNOWN_GRADERS.get(gid) != gver:
        _fail("task.grader", f"unknown grader {gid!r} version {gver!r}; known {KNOWN_GRADERS}")
    _keys(task, "task", (*TASK_COMMON, *TASK_SPECIFIC[gid]))
    for f in ("task_id", "version", "description", "environment", "provenance", "license"):
        _str(task[f], f"task.{f}")
    if not isinstance(task["visible_checks"], list) or not all(isinstance(c, str) for c in task["visible_checks"]):
        _fail("task.visible_checks", "must be a list of strings")
    if gid == "sort-check":
        if not isinstance(task["input"], list) or not task["input"]:
            _fail("task.input", "must be a non-empty list")
        for i, v in enumerate(task["input"]):
            _int(v, f"task.input[{i}]", -2**53)
    else:
        b = task["bundle"]
        trees = BUNDLE_TREES[gid]
        _keys(b, "task.bundle", (*(f"{t}_digest" for t in trees), "scope", "hidden_test_count", "timeout_seconds"))
        for t in trees:
            _str(b[f"{t}_digest"], f"task.bundle.{t}_digest")
        if not isinstance(b["scope"], list) or not b["scope"] or not all(isinstance(x, str) and x for x in b["scope"]):
            _fail("task.bundle.scope", "must be a non-empty list of relative paths")
        _int(b["hidden_test_count"], "task.bundle.hidden_test_count", 1)
        _int(b["timeout_seconds"], "task.bundle.timeout_seconds", 1, 3600)
    return task


def fake_candidate_kinds(task, bundle_dir):
    if task["grader"]["id"] == "sort-check":
        return set(FAKE_CANDIDATES)
    return {p.stem for p in (Path(bundle_dir) / "reference").glob("*.patch")}


def verify_bundle(task, bundle_dir):
    """For patch tasks: base and hidden trees must match the digests pinned in task.json."""
    for part in BUNDLE_TREES.get(task["grader"]["id"], ()):
        actual = tree_digest(Path(bundle_dir) / part)
        if actual != task["bundle"][f"{part}_digest"]:
            _fail(f"task.bundle.{part}_digest", f"bundle {part}/ is {actual}, task pins {task['bundle'][part + '_digest']}")


def validate_config(c, path):
    _keys(c, path, CONFIG_REQUIRED, CONFIG_NULLABLE)
    for f in ("config_id", "model_requested", "workflow", "isolation_track"):
        _str(c[f], f"{path}.{f}")
    if not CONFIG_ID.fullmatch(c["config_id"]):
        _fail(f"{path}.config_id", f"must match {CONFIG_ID.pattern}")
    for f in ("model_resolved", "cli", "cli_version", "prompt_digest"):
        _str(c[f], f"{path}.{f}", nullable=True)
    for f in ("reasoning", "sampling"):
        if c[f] is not None and not isinstance(c[f], dict):
            _fail(f"{path}.{f}", "must be an object or null")
    if not isinstance(c["tool_permissions"], list) or not all(isinstance(t, str) for t in c["tool_permissions"]):
        _fail(f"{path}.tool_permissions", "must be a list of strings")
    _keys(c["budget"], f"{path}.budget", ("max_wall_seconds",))
    _int(c["budget"]["max_wall_seconds"], f"{path}.budget.max_wall_seconds", 1, 86400)  # contract timeout_seconds


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
    _int(m["retry_policy"]["max_attempts"], "manifest.retry_policy.max_attempts", 1, 100)  # contract max_attempts
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
    _enum(ex.get("kind") if isinstance(ex, dict) else None, "manifest.executor.kind", ("fake", "agent-cli"))
    if ex["kind"] == "agent-cli":  # real CLI runs: nothing scripted, every config names its CLI
        _keys(ex, "manifest.executor", ("kind",))
        for i, c in enumerate(m["configs"]):
            _enum(c["cli"], f"manifest.configs[{i}].cli", AGENT_CLIS)
            if c["isolation_track"] != CONTROLLED_TRACK:
                _fail(f"manifest.configs[{i}].isolation_track", f"agent-cli executor requires {CONTROLLED_TRACK!r}")
        return m
    _keys(ex, "manifest.executor", ("kind", "script"))
    for i, c in enumerate(m["configs"]):
        if c["isolation_track"] != FAKE_TRACK:
            _fail(f"manifest.configs[{i}].isolation_track", f"fake executor requires {FAKE_TRACK!r}")
    if not isinstance(ex["script"], list):
        _fail("manifest.executor.script", "must be a list")
    seen = set()
    for i, e in enumerate(ex["script"]):
        p = f"manifest.executor.script[{i}]"
        _keys(e, p, ("config_id", "repetition", "outcome", "candidate", "completion", "usage"))
        if e["config_id"] not in ids:
            _fail(f"{p}.config_id", f"binding to unknown config {e['config_id']!r}")
        _int(e["repetition"], f"{p}.repetition", 1, m["repetitions"])
        _enum(e["outcome"], f"{p}.outcome", OUTCOMES)
        _str(e["candidate"], f"{p}.candidate", nullable=True)
        _enum(e["completion"], f"{p}.completion", COMPLETION, nullable=True)
        if e["usage"] is not None:
            _keys(e["usage"], f"{p}.usage", ("units", "cache_semantics"))
            validate_units(e["usage"]["units"], f"{p}.usage.units")
            _enum(e["usage"]["cache_semantics"], f"{p}.usage.cache_semantics", CACHE_SEMANTICS)
        if e["outcome"] == "completed" and e["candidate"] is None:
            _fail(p, "outcome 'completed' without a candidate")
        if e["completion"] is not None and e["outcome"] != "completed":
            _fail(p, "only a completed execution can carry a completion decision")
        if e["outcome"] == "rejected" and (e["candidate"] is not None or e["usage"] is not None):
            _fail(p, "a rejected request was never launched: no candidate, no usage")
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
    task = validate_task(_json(task_bytes, str(task_path)))
    verify_bundle(task, task_path.parent)
    kinds = fake_candidate_kinds(task, task_path.parent)
    for i, e in enumerate(m["executor"].get("script", [])):
        if e["candidate"] is not None and e["candidate"] not in kinds:
            _fail(f"manifest.executor.script[{i}].candidate", f"{e['candidate']!r} not available; known {sorted(kinds)}")
    return m, task, manifest_bytes, task_bytes


def validate_event(e, path):
    _version(e, path, EVENT_VERSION)
    if e.get("type") not in EVENT_FIELDS:
        _fail(f"{path}.type", f"unknown event type {e.get('type')!r}")
    _keys(e, path, ("schema_version", "type", "event_id", *EVENT_FIELDS[e["type"]]))
    _str(e["event_id"], f"{path}.event_id")
    if e["type"] == "trial_finished":
        _enum(e["source"], f"{path}.source", TERMINAL_SOURCES)
        _enum(e["outcome"], f"{path}.outcome", OUTCOMES)
        _enum(e["completion"], f"{path}.completion", COMPLETION, nullable=True)
        _enum(e["error_code"], f"{path}.error_code", (*ERROR_CODES, LIMIT_EXCEEDED), nullable=True)
        if e["target"] is not None:
            _keys(e["target"], f"{path}.target", ("id", "qualification_digest", "image_digest"))
        if e["limits"] is not None:
            _keys(e["limits"], f"{path}.limits", ("applied", "fired", "output_truncated"))
            _enum(e["limits"]["fired"], f"{path}.limits.fired", FIRED_LIMITS, nullable=True)
        if not isinstance(e["attempts"], list):
            _fail(f"{path}.attempts", "must be a list")
        for i, a in enumerate(e["attempts"]):
            _keys(a, f"{path}.attempts[{i}]", ("attempt_id", "outcome", "started_at", "ended_at"))
            _str(a["attempt_id"], f"{path}.attempts[{i}].attempt_id")
    if e["type"] == "usage":
        _str(e["attempt_id"], f"{path}.attempt_id")
        _str(e["usage_event_id"], f"{path}.usage_event_id")
        _enum(e["kind"], f"{path}.kind", USAGE_KINDS)
        validate_units(e["units"], f"{path}.units")
        _enum(e["cache_semantics"], f"{path}.cache_semantics", CACHE_SEMANTICS)
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
