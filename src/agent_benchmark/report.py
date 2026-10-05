"""Deterministic report from recorded events only. Never executes a model or the executor.

Same run directory -> byte-identical report.md / report.csv / summary.json.
"""
import csv
import io
import json
import math
from pathlib import Path

from .schema import OUTCOMES, GRADES, ValidationError, digest, validate_event, validate_manifest, validate_task, _json

FAKE_BANNER = ("FAKE EXECUTION (offline, scripted outcomes). Not a measurement of any model, CLI or backend; "
               "says nothing about qualified/live behaviour.")
LIMITATIONS = [
    "Single synthetic task: repetitions of one task do not generalise to other tasks.",
    "Grader runs in-process on a data-only candidate; transparent diagnostic track, no hidden tests or sandbox.",
    "Cost is not computed (pricing arrives in AB5-04); token totals are known subtotals with coverage, not full usage.",
    "Durations are wall time of the fake call, not of any real model; latency is shown conditional on PASS.",
    "Small samples: raw values, median and range only; Wilson 95% interval assumes independent trials.",
]


def wilson95(k, n):
    if n == 0:
        return None
    z = 1.959963984540054
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def _median(xs):
    if not xs:
        return None
    xs = sorted(xs)
    mid = len(xs) // 2
    return xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2


def load_run(run_dir):
    run_dir = Path(run_dir)
    manifest_bytes = (run_dir / "manifest.json").read_bytes()
    task_bytes = (run_dir / "task.json").read_bytes()
    manifest = validate_manifest(_json(manifest_bytes, "manifest.json"), digest(task_bytes))
    task = validate_task(_json(task_bytes, "task.json"))
    events_bytes = (run_dir / "events.jsonl").read_bytes()
    events = [validate_event(_json(line, f"events.jsonl:{i}"), f"events.jsonl:{i}")
              for i, line in enumerate(events_bytes.splitlines(), 1) if line.strip()]
    if not events or events[0]["type"] != "run_started":
        raise ValidationError("events.jsonl: first record must be run_started")
    if events[0]["manifest_digest"] != digest(manifest_bytes) or events[0]["task_digest"] != digest(task_bytes):
        raise ValidationError("events.jsonl: run_started digests do not match manifest.json/task.json")
    inputs = {"manifest": digest(manifest_bytes), "task": digest(task_bytes), "events": digest(events_bytes)}
    return manifest, task, events, inputs


def trials(events):
    """One row per started trial; a start without a finish stays visible as outcome 'unknown' (interrupted)."""
    rows = {}
    for e in events:
        tid = e.get("trial_id")
        if e["type"] == "trial_started":
            if tid in rows:
                raise ValidationError(f"events.jsonl: trial {tid} started twice")
            rows[tid] = {"trial_id": tid, "config_id": e["config_id"], "repetition": e["repetition"],
                         "outcome": "unknown", "interrupted": True, "harness_completion": None,
                         "candidate_digest": None, "grade": None, "duration_ms": None, "usage": None,
                         "measurement_quality": "unknown"}
        elif e["type"] == "trial_finished":
            r = rows.get(tid)
            if r is None or not r["interrupted"]:
                raise ValidationError(f"events.jsonl: trial_finished for {tid} without a single open start")
            r.update(interrupted=False, outcome=e["outcome"], harness_completion=e["harness_completion"],
                     candidate_digest=e["candidate_digest"], duration_ms=e["duration_ms"], usage=e["usage"],
                     measurement_quality=e["measurement_quality"])
        elif e["type"] == "grade":
            r = rows.get(tid)
            if r is None or r["grade"] is not None or e["candidate_digest"] != r["candidate_digest"]:
                raise ValidationError(f"events.jsonl: grade for {tid} not bound to exactly one sealed candidate")
            r["grade"] = e["result"]
    return list(rows.values())


def summarize(manifest, task, events, inputs):
    rows = trials(events)
    graders = sorted({json.dumps(e["grader"], sort_keys=True) for e in events if e["type"] == "grade"})
    configs = []
    for c in manifest["configs"]:
        rs = [r for r in rows if r["config_id"] == c["config_id"]]
        n = len(rs)
        passes = sum(r["grade"] == "PASS" for r in rs)
        pass_ms = sorted(r["duration_ms"] for r in rs if r["grade"] == "PASS")
        usage_known = [r["usage"] for r in rs if r["usage"]]
        configs.append({
            "config_id": c["config_id"],
            "config_digest": digest(json.dumps(c, sort_keys=True).encode()),
            "model_requested": c["model_requested"],
            "workflow": c["workflow"],
            "isolation_track": c["isolation_track"],
            "started": n,
            "interrupted": sum(r["interrupted"] for r in rs),
            "outcomes": {o: sum(r["outcome"] == o for r in rs) for o in OUTCOMES},
            "grades": {g: sum(r["grade"] == g for r in rs) for g in GRADES},
            "ungraded": sum(r["grade"] is None for r in rs),
            "harness_success_not_pass": sum(r["harness_completion"] == "success" and r["grade"] != "PASS" for r in rs),
            "operational_success": {"pass": passes, "denominator": n, "denominator_definition": "all started trials",
                                    "rate": round(passes / n, 4) if n else None, "wilson95": wilson95(passes, n)},
            "pass_duration_ms": {"conditional_on": "PASS", "values": pass_ms, "median": _median(pass_ms),
                                 "min": pass_ms[0] if pass_ms else None, "max": pass_ms[-1] if pass_ms else None},
            "usage": {
                "coverage": {q: sum(r["measurement_quality"] == q for r in rs) for q in ("complete", "partial", "unknown")},
                "known_subtotal": {f: sum(u[f] for u in usage_known if u[f] is not None)
                                   for f in ("input_tokens", "output_tokens", "cache_read_tokens")},
                "known_subtotal_is_full_usage": n > 0 and all(r["measurement_quality"] == "complete" for r in rs),
            },
            "cost": None,
        })
    return {
        "fake_execution": True,
        "banner": FAKE_BANNER,
        "run_id": events[0]["run_id"],
        "experiment_id": manifest["experiment_id"],
        "run_complete": events[-1]["type"] == "run_finished",
        "input_digests": inputs,
        "graders": [json.loads(g) for g in graders],
        "exclusions": [],
        "configs": configs,
        "trials": rows,
        "limitations": LIMITATIONS,
    }


def _fmt(v):
    return "unknown" if v is None else str(v)


def render_markdown(s):
    out = [f"# Benchmark report: {s['experiment_id']}", "", f"> **{s['banner']}**", "",
           f"- run_id: `{s['run_id']}`", f"- run complete: {s['run_complete']}",
           *[f"- input {k} digest: `{v}`" for k, v in s["input_digests"].items()],
           *[f"- grader: `{g['id']}` v{g['version']} `{g['digest']}`" for g in s["graders"]],
           "- exclusions: none (operational success denominator = all started trials)", "",
           "## Per configuration", "",
           "| config | track | started | completed/timeout/cancel/error/unknown | PASS/FAIL/INVALID/ungraded "
           "| success (Wilson 95%) | harness success but not PASS | PASS duration ms median [min-max] "
           "| usage complete/partial/unknown | known tokens in/out | cost |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in s["configs"]:
        o, g, sr, d, u = c["outcomes"], c["grades"], c["operational_success"], c["pass_duration_ms"], c["usage"]
        ci = "n/a" if sr["wilson95"] is None else f"[{sr['wilson95'][0]}, {sr['wilson95'][1]}]"
        sub = "known subtotal" if not u["known_subtotal_is_full_usage"] else "full"
        out.append(
            f"| `{c['config_id']}` | {c['isolation_track']} | {c['started']} "
            f"| {'/'.join(str(o[k]) for k in OUTCOMES)} "
            f"| {g['PASS']}/{g['FAIL']}/{g['INVALID']}/{c['ungraded']} "
            f"| {sr['pass']}/{sr['denominator']} {ci} | {c['harness_success_not_pass']} "
            f"| {_fmt(d['median'])} [{_fmt(d['min'])}-{_fmt(d['max'])}] "
            f"| {u['coverage']['complete']}/{u['coverage']['partial']}/{u['coverage']['unknown']} "
            f"| {u['known_subtotal']['input_tokens']}/{u['known_subtotal']['output_tokens']} ({sub}) "
            f"| {_fmt(c['cost'])} |")
    out += ["", "## Limitations", "", *[f"- {x}" for x in s["limitations"]], ""]
    return "\n".join(out)


CSV_FIELDS = ("fake_execution", "trial_id", "config_id", "repetition", "outcome", "interrupted",
              "harness_completion", "grade", "candidate_digest", "duration_ms", "measurement_quality",
              "input_tokens", "output_tokens", "cache_read_tokens")


def render_csv(s):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_FIELDS)
    for r in s["trials"]:
        u = r["usage"] or {}
        w.writerow(["true" if s["fake_execution"] else "false", *(_fmt(r[k]) for k in CSV_FIELDS[1:11]),
                    *(_fmt(u.get(k)) for k in CSV_FIELDS[11:])])
    return buf.getvalue()


def write_report(run_dir):
    run_dir = Path(run_dir)
    s = summarize(*load_run(run_dir))
    (run_dir / "summary.json").write_text(json.dumps(s, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "report.md").write_text(render_markdown(s), encoding="utf-8")
    (run_dir / "report.csv").write_text(render_csv(s), encoding="utf-8")
    return s
