"""Deterministic report from recorded events only. Never executes a model or the executor.

Same run directory -> byte-identical report.md / report.csv / summary.json.
"""
import csv
import io
import json
import math
from decimal import Decimal
from pathlib import Path

from .pricing import fmt, price_usage, validate_pricing
from .schema import (GRADES, OUTCOMES, USAGE_FIELDS, ValidationError, _json, digest, validate_event,
                     validate_manifest, validate_task)

FAKE_BANNER = ("FAKE EXECUTION (offline, scripted outcomes). Not a measurement of any model, CLI or backend; "
               "says nothing about qualified/live behaviour.")
LIMITATIONS = [
    "Single synthetic task: repetitions of one task do not generalise to other tasks.",
    "Grader runs in-process on a data-only candidate; transparent diagnostic track, no hidden tests or sandbox.",
    "Cost is an estimate from a dated pricing snapshot x recorded usage, not an invoice; no currency conversion.",
    "Wall time covers the execution call only; queue/setup and grading time are not measured yet.",
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


def bind_pricing(run_dir, pricing_path):
    """Copy a pricing snapshot into the run once; a different snapshot for the same run is refused."""
    data = Path(pricing_path).read_bytes()
    validate_pricing(_json(data, str(pricing_path)))
    target = Path(run_dir) / "pricing.json"
    if target.exists() and target.read_bytes() != data:
        raise ValidationError(f"{target}: run already bound to a different pricing snapshot")
    target.write_bytes(data)


def load_pricing(run_dir):
    path = Path(run_dir) / "pricing.json"
    if not path.is_file():
        return None, None
    data = path.read_bytes()
    return validate_pricing(_json(data, str(path))), digest(data)


def _cost(c, rs, passes, pricing):
    """Cost of all started trials of one config. Totals only when every trial is fully priced."""
    if pricing is None:
        return {"status": "no pricing snapshot", "total": None, "per_pass": None}
    priced_by = "model_resolved" if c["model_resolved"] else "model_requested"
    model_id = c[priced_by]
    model = pricing["models"].get(model_id)
    base = {"model_id": model_id, "priced_by": priced_by, "basis": pricing["basis"]}
    if model is None:
        return {**base, "status": f"no rate for model {model_id!r}", "currency": None, "total": None,
                "per_pass": None, "known_subtotal": None,
                "coverage": {"full": 0, "partial": 0, "unknown": len(rs)}}
    priced = [price_usage(r["usage"], model) for r in rs]
    known = [a for a, _ in priced if a is not None]
    full = sum(f for _, f in priced)
    total = sum(known, Decimal(0)) if known and full == len(rs) else None
    if total is None:
        per_pass, note = None, "incomplete cost: full cost of all started trials unknown"
    elif passes == 0:
        per_pass, note = None, "no successful solution (0 PASS)"
    else:
        per_pass, note = total / passes, "all started trials' cost / PASS"
    return {**base, "status": "estimate", "currency": model["currency"],
            "coverage": {"full": full, "partial": sum(1 for a, f in priced if a is not None and not f),
                         "unknown": sum(1 for a, _ in priced if a is None)},
            "known_subtotal": fmt(sum(known, Decimal(0))) if known else None,
            "total": fmt(total), "per_pass": fmt(per_pass), "per_pass_note": note}


def _sum_usage(items):
    """Sum usage dicts; a field stays unknown (None) only when no item knows it."""
    return {f: (sum(u[f] for u in items if u[f] is not None) if any(u[f] is not None for u in items) else None)
            for f in USAGE_FIELDS}


def reduce_events(events):
    """Fold the append-only ledger into one row per started trial.

    First record wins; every disagreement is kept in `conflicts` instead of overwriting history:
    - identical re-delivered event (same event_id, same body) is ignored; same event_id, other body is a conflict
    - a second terminal or grade for a trial is a conflict and does not replace the first
    - usage: dedup by usage_event_id; per attempt a `summary` supersedes `stream` events (no double counting)
    - a start without a terminal stays visible as outcome 'unknown' (interrupted)
    """
    seen, rows, conflicts, usage = {}, {}, [], {}

    def conflict(kind, e, detail):
        conflicts.append({"kind": kind, "event_id": e["event_id"], "trial_id": e.get("trial_id"), "detail": detail})

    for e in events:
        if e["event_id"] in seen:
            if seen[e["event_id"]] != e:
                conflict("event_id_reused", e, "same event_id with a different body; first kept")
            continue
        seen[e["event_id"]] = e
        t, tid = e["type"], e.get("trial_id")
        r = rows.get(tid)
        if t == "trial_started":
            if r is not None:
                conflict("duplicate_start", e, "trial already started; first kept")
                continue
            rows[tid] = {"trial_id": tid, "config_id": e["config_id"], "repetition": e["repetition"],
                         "request_id": e["request_id"], "replaces": e["replaces"], "outcome": "unknown",
                         "interrupted": True, "terminal_source": None, "attempt_ids": [],
                         "harness_completion": None, "candidate_digest": None, "original_grade": None,
                         "grade": None, "corrections": [], "duration_ms": None, "usage": None,
                         "measurement_quality": "unknown"}
        elif t in ("trial_finished", "usage", "grade", "correction") and r is None:
            conflict("orphan", e, f"{t} for a trial that was never started; ignored")
        elif t == "trial_finished":
            if e["request_id"] != r["request_id"]:
                conflict("wrong_request", e, "terminal for another request_id; ignored")
            elif not r["interrupted"]:
                conflict("conflicting_terminal", e, f"second terminal ({e['outcome']}) ignored; first kept")
            else:
                r.update(interrupted=False, outcome=e["outcome"], terminal_source=e["source"],
                         attempt_ids=[a["attempt_id"] for a in e["attempts"]],
                         harness_completion=e["harness_completion"], candidate_digest=e["candidate_digest"],
                         duration_ms=e["duration_ms"])
        elif t == "usage":
            per_trial = usage.setdefault(tid, {})
            prev = per_trial.get(e["usage_event_id"])
            if prev is not None:
                if (prev["kind"], prev["attempt_id"], prev["usage"]) != (e["kind"], e["attempt_id"], e["usage"]):
                    conflict("usage_event_id_reused", e, "same usage_event_id with a different body; first kept")
                continue
            per_trial[e["usage_event_id"]] = e
        elif t == "grade":
            if r["original_grade"] is not None:
                conflict("duplicate_grade", e, "second grade ignored; first kept")
            elif e["candidate_digest"] != r["candidate_digest"]:
                conflict("unbound_grade", e, "grade not bound to the sealed candidate digest; ignored")
            else:
                r["original_grade"] = e["result"]
        elif t == "correction":
            r["corrections"].append({"action": e["action"], "reason": e["reason"]})

    for tid, r in rows.items():
        r["grade"] = "INVALID" if r["corrections"] and r["original_grade"] is not None else r["original_grade"]
        by_attempt = {}
        for e in usage.get(tid, {}).values():
            if r["attempt_ids"] and e["attempt_id"] not in r["attempt_ids"]:
                conflict("unknown_attempt", e, "usage for an attempt not in the trial terminal; ignored")
                continue
            by_attempt.setdefault(e["attempt_id"], []).append(e)
        scoped = []
        for aid, evs in by_attempt.items():
            summaries = [e for e in evs if e["kind"] == "summary"]
            if len(summaries) > 1:
                conflict("multiple_summaries", summaries[1], f"attempt {aid}: more than one summary; first kept")
            scoped.append(summaries[0]["usage"] if summaries else
                          {**_sum_usage([e["usage"] for e in evs]),
                           "completeness": "complete" if all(e["usage"]["completeness"] == "complete" for e in evs)
                           else "partial"})
        if scoped:
            missing_attempt = any(a not in by_attempt for a in r["attempt_ids"])
            complete = all(u["completeness"] == "complete" for u in scoped) and not missing_attempt
            r["usage"] = _sum_usage(scoped)
            r["measurement_quality"] = "complete" if complete else "partial"
    return {"trials": list(rows.values()), "conflicts": conflicts}


def summarize(manifest, task, events, inputs, pricing=None, pricing_digest=None):
    state = reduce_events(events)
    rows = state["trials"]
    graders = sorted({json.dumps(e["grader"], sort_keys=True) for e in events if e["type"] == "grade"})
    configs = []
    for c in manifest["configs"]:
        rs = [r for r in rows if r["config_id"] == c["config_id"]]
        n = len(rs)
        passes = sum(r["grade"] == "PASS" for r in rs)
        pass_ms = sorted(r["duration_ms"] for r in rs if r["grade"] == "PASS" and r["duration_ms"] is not None)
        usage_known = [r["usage"] for r in rs if r["usage"]]
        excluded_outcomes = {x["outcome"] for x in manifest["exclusions"]}
        excluded = sum(r["outcome"] in excluded_outcomes for r in rs)
        configs.append({
            "config_id": c["config_id"],
            "config_digest": digest(json.dumps(c, sort_keys=True).encode()),
            "model_requested": c["model_requested"],
            "workflow": c["workflow"],
            "isolation_track": c["isolation_track"],
            "started": n,
            "interrupted": sum(r["interrupted"] for r in rs),
            "reconciled_unknown": sum(r["terminal_source"] == "reconciliation" for r in rs),
            "replacements": sum(r["replaces"] is not None for r in rs),
            "corrected": sum(bool(r["corrections"]) for r in rs),
            "outcomes": {o: sum(r["outcome"] == o for r in rs) for o in OUTCOMES},
            "grades": {g: sum(r["grade"] == g for r in rs) for g in GRADES},
            "ungraded": sum(r["grade"] is None for r in rs),
            "harness_success_not_pass": sum(r["harness_completion"] == "success" and r["grade"] != "PASS" for r in rs),
            "operational_success": {"pass": passes, "denominator": n, "denominator_definition": "all started trials",
                                    "rate": round(passes / n, 4) if n else None, "wilson95": wilson95(passes, n)},
            "success_after_exclusions": None if not excluded_outcomes else {
                "pass": sum(r["grade"] == "PASS" and r["outcome"] not in excluded_outcomes for r in rs),
                "denominator": n - excluded, "excluded": excluded,
                "denominator_definition": f"started trials minus outcomes {sorted(excluded_outcomes)} (predeclared)",
                "wilson95": wilson95(sum(r["grade"] == "PASS" and r["outcome"] not in excluded_outcomes
                                         for r in rs), n - excluded)},
            "first_attempt_pass": sum(r["grade"] == "PASS" and len(r["attempt_ids"]) == 1 for r in rs),
            "after_retry_pass": sum(r["grade"] == "PASS" and len(r["attempt_ids"]) > 1 for r in rs),
            "pass_duration_ms": {"conditional_on": "PASS", "values": pass_ms, "median": _median(pass_ms),
                                 "min": pass_ms[0] if pass_ms else None, "max": pass_ms[-1] if pass_ms else None},
            "usage": {
                "coverage": {q: sum(r["measurement_quality"] == q for r in rs) for q in ("complete", "partial", "unknown")},
                "known_subtotal": {f: sum(u[f] for u in usage_known if u[f] is not None)
                                   for f in ("input_tokens", "output_tokens", "cache_read_tokens")},
                "known_subtotal_is_full_usage": n > 0 and all(r["measurement_quality"] == "complete" for r in rs),
            },
            "cost": _cost(c, rs, passes, pricing),
        })
    currencies = {c["cost"].get("currency") for c in configs}
    return {
        "fake_execution": True,
        "banner": FAKE_BANNER,
        "run_id": events[0]["run_id"],
        "experiment_id": manifest["experiment_id"],
        "run_complete": events[-1]["type"] == "run_finished",
        "input_digests": {**inputs, **({"pricing": pricing_digest} if pricing_digest else {})},
        "pricing": None if pricing is None else {k: pricing[k] for k in ("snapshot_utc", "source", "basis")},
        "cost_comparable": (pricing is not None and len(currencies) == 1 and None not in currencies
                            and all(c["cost"]["total"] is not None for c in configs)),
        "integrity": {"ok": not state["conflicts"], "conflicts": state["conflicts"]},
        "graders": [json.loads(g) for g in graders],
        "exclusions": manifest["exclusions"],
        "configs": configs,
        "trials": rows,
        "limitations": LIMITATIONS,
    }


def _fmt(v):
    return "unknown" if v is None else str(v)


def _money(v, cost):
    return "unknown" if v is None else f"{v} {cost['currency']}"


def _cost_cell(cost):
    if cost["total"] is not None:
        return f"{_money(cost['total'], cost)} ({cost['status']})"
    return "unknown (incomplete)" if cost["status"] == "estimate" else f"unknown ({cost['status']})"


def render_markdown(s):
    out = [f"# Benchmark report: {s['experiment_id']}", "", f"> **{s['banner']}**", "",
           f"- run_id: `{s['run_id']}`", f"- run complete: {s['run_complete']}",
           *[f"- input {k} digest: `{v}`" for k, v in s["input_digests"].items()],
           *[f"- grader: `{g['id']}` v{g['version']} `{g['digest']}`" for g in s["graders"]],
           "- operational success denominator: all started trials, incl. reconciled and replaced ones",
           "- exclusions (secondary metric only): " + (", ".join(f"{x['outcome']} ({x['reason']})"
                                                         for x in s["exclusions"]) or "none"),
           "- pricing: " + ("none (cost unknown)" if s["pricing"] is None else
                            f"{s['pricing']['basis']} snapshot {s['pricing']['snapshot_utc']} from {s['pricing']['source']}"),
           f"- integrity: {'ok' if s['integrity']['ok'] else str(len(s['integrity']['conflicts'])) + ' conflict(s), first record kept'}",
           "",
           "## Per configuration", "",
           "| config | track | started | completed/timeout/cancel/error/unknown | PASS/FAIL/INVALID/ungraded "
           "| success (Wilson 95%) | harness success but not PASS | PASS duration ms median [min-max] "
           "| usage complete/partial/unknown | known tokens in/out | interrupted/reconciled/replacements/corrected "
           "| cost |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
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
            f"| {c['interrupted']}/{c['reconciled_unknown']}/{c['replacements']}/{c['corrected']} "
            f"| {_cost_cell(c['cost'])} |")
    if s["integrity"]["conflicts"]:
        out += ["", "## Integrity conflicts", "",
                *[f"- {x['kind']} trial `{x['trial_id']}` event `{x['event_id']}`: {x['detail']}"
                  for x in s["integrity"]["conflicts"]]]
    out += ["", "## Success and cost detail", "",
            "| config | first-attempt PASS | after-retry PASS | success after exclusions | cost coverage full/partial/unknown "
            "| known cost subtotal | cost per PASS |", "|---|---|---|---|---|---|---|"]
    for c in s["configs"]:
        x, k = c["success_after_exclusions"], c["cost"]
        excl = "n/a (no exclusions)" if x is None else f"{x['pass']}/{x['denominator']} (excluded {x['excluded']})"
        cov = k.get("coverage")
        out.append(f"| `{c['config_id']}` | {c['first_attempt_pass']} | {c['after_retry_pass']} | {excl} "
                   f"| {'n/a' if not cov else '/'.join(str(cov[q]) for q in ('full', 'partial', 'unknown'))} "
                   f"| {_money(k.get('known_subtotal'), k)} | {_money(k['per_pass'], k)} "
                   f"({k.get('per_pass_note', k['status'])}) |")
    out.append(f"\nCost comparable across configs: {s['cost_comparable']}")
    corrections = [(r["trial_id"], x) for r in s["trials"] for x in r["corrections"]]
    if corrections:
        out += ["", "## Corrections", "", *[f"- `{t}` {x['action']}: {x['reason']}" for t, x in corrections]]
    out += ["", "## Limitations", "", *[f"- {x}" for x in s["limitations"]], ""]
    return "\n".join(out)


CSV_FIELDS = ("fake_execution", "trial_id", "config_id", "repetition", "replaces", "outcome", "terminal_source",
              "interrupted", "harness_completion", "original_grade", "grade", "candidate_digest", "duration_ms",
              "measurement_quality", "input_tokens", "output_tokens", "cache_read_tokens")


def render_csv(s):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_FIELDS)
    for r in s["trials"]:
        u = r["usage"] or {}
        w.writerow(["true" if s["fake_execution"] else "false", *(_fmt(r[k]) for k in CSV_FIELDS[1:14]),
                    *(_fmt(u.get(k)) for k in CSV_FIELDS[14:])])
    return buf.getvalue()


def write_report(run_dir, pricing_path=None):
    run_dir = Path(run_dir)
    if pricing_path is not None:
        bind_pricing(run_dir, pricing_path)
    s = summarize(*load_run(run_dir), *load_pricing(run_dir))
    (run_dir / "summary.json").write_text(json.dumps(s, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "report.md").write_text(render_markdown(s), encoding="utf-8")
    (run_dir / "report.csv").write_text(render_csv(s), encoding="utf-8")
    return s
