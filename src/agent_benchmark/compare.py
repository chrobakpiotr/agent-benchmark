"""AB5-08: compare two recorded runs, and say first whether the comparison means anything.

Built only from recorded files (`load_run`, `summarize`). A changed task, grader, executor or config identity makes a
config pair "not comparable"; such a pair never gets a difference claim. A PASS-rate difference is claimed only when
the Wilson 95% intervals do not overlap; Fisher's exact two-sided p-value is reported alongside as information, not
as the decision rule. Cost is compared only when both sides are fully priced in one currency and their PASS rates
show no difference (correctness before cost). `pool` adds up runs of identical task, grader, executor, backend and
config identity; any other run is listed as excluded, never silently merged.
"""
import json
import math
from pathlib import Path

from .report import load_pricing, load_run, summarize

CONFIG_IDENTITY = ("model_requested", "cli", "cli_version", "prompt_digest", "reasoning", "sampling",
                   "tool_permissions", "workflow", "reviewer", "budget", "isolation_track")


def _harness_versions(run_dir):
    seen = set()
    for p in sorted(Path(run_dir).glob("evidence/*/result.json")):
        versions = json.loads(p.read_text()).get("versions") or {}
        seen.update(f"{k} {v}" for k, v in versions.items())
    return sorted(seen)


def _side(run_dir):
    manifest, task, events, inputs = load_run(run_dir)
    s = summarize(manifest, task, events, inputs, *load_pricing(run_dir))
    return {"run_dir": str(run_dir), "experiment_id": s["experiment_id"], "summary": s,
            "task": inputs["task"], "graders": s["graders"], "executor": events[0]["executor"],
            "versions": _harness_versions(run_dir), "pricing": s["input_digests"].get("pricing"),
            "configs": {c["config_id"]: c for c in manifest["configs"]}}


def fisher_exact(k1, n1, k2, n2):
    """Two-sided Fisher exact test for PASS k1/n1 vs k2/n2: total probability of tables at most as likely."""
    if not n1 or not n2:
        return None
    k, n = k1 + k2, n1 + n2

    def prob(x):
        return math.comb(n1, x) * math.comb(n2, k - x) / math.comb(n, k)
    observed = prob(k1)
    return round(min(1.0, sum(prob(x) for x in range(max(0, k - n2), min(k, n1) + 1)
                              if prob(x) <= observed * (1 + 1e-9))), 4)


def _overlap(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def compare(run_a, run_b):
    a, b = _side(run_a), _side(run_b)
    run_reasons = []
    if a["task"] != b["task"]:
        run_reasons.append("task changed")
    if a["graders"] != b["graders"]:
        run_reasons.append("grader changed")
    if a["executor"] != b["executor"]:
        run_reasons.append("executor changed")
    if a["versions"] != b["versions"]:
        run_reasons.append("execution backend version changed")
    stats = {s["config_id"]: s for s in a["summary"]["configs"]}, {s["config_id"]: s for s in b["summary"]["configs"]}
    pairs = []
    for cid in sorted(set(a["configs"]) | set(b["configs"])):
        if cid not in a["configs"] or cid not in b["configs"]:
            pairs.append({"config_id": cid, "comparable": False, "reasons": ["config present in one run only"]})
            continue
        reasons = run_reasons + [f"{f} changed" for f in CONFIG_IDENTITY if a["configs"][cid].get(f) != b["configs"][cid].get(f)]
        sa, sb = stats[0][cid], stats[1][cid]
        wa, wb = sa["operational_success"]["wilson95"], sb["operational_success"]["wilson95"]
        oa, ob = sa["operational_success"], sb["operational_success"]
        pair = {"config_id": cid, "comparable": not reasons, "reasons": reasons,
                "pass": [f"{s['operational_success']['pass']}/{s['operational_success']['denominator']}" for s in (sa, sb)],
                "wilson95": [wa, wb],
                "fisher_p": fisher_exact(oa["pass"], oa["denominator"], ob["pass"], ob["denominator"]) if not reasons else None,
                "pass_duration_median_ms": [s["pass_duration_ms"]["median"] for s in (sa, sb)],
                "tokens_processed_in_out": [[s["usage"]["processed_input_tokens"], s["usage"]["known_subtotal"]["output_tokens"]]
                                            for s in (sa, sb)],
                "cost_status": [s["cost"]["status"] for s in (sa, sb)]}
        if reasons:
            pair["correctness"] = "not compared: " + "; ".join(reasons)
        elif None in (wa, wb) or _overlap(wa, wb):
            pair["correctness"] = "no evidence of a difference"
        else:
            pair["correctness"] = "B higher" if wb[0] > wa[1] else "B lower"
        priced = all(s["cost"]["total"] is not None for s in (sa, sb)) and sa["cost"].get("currency") == sb["cost"].get("currency")
        if not pair["comparable"]:
            pair["cost"] = "not compared: configs not comparable"
        elif pair["correctness"] != "no evidence of a difference":
            pair["cost"] = "not compared: PASS rates differ (correctness first)"
        elif a["pricing"] is None or b["pricing"] is None or not priced:
            pair["cost"] = "not compared: not fully priced on both sides"
        else:
            pair["cost"] = f"A {sa['cost']['total']} vs B {sb['cost']['total']} {sa['cost']['currency']}"
        pairs.append(pair)
    return {"run_a": {k: a[k] for k in ("run_dir", "experiment_id", "task", "versions", "pricing")},
            "run_b": {k: b[k] for k in ("run_dir", "experiment_id", "task", "versions", "pricing")},
            "run_level_differences": run_reasons, "configs": pairs}


def render_markdown(c):
    out = [f"# Comparison: {c['run_a']['experiment_id']} (A) vs {c['run_b']['experiment_id']} (B)", "",
           f"- A: `{c['run_a']['run_dir']}`", f"- B: `{c['run_b']['run_dir']}`",
           f"- run-level differences: {', '.join(c['run_level_differences']) or 'none'}", "",
           "| config | comparable | PASS A / B | Wilson95 A / B | correctness | Fisher p | PASS median ms A / B "
           "| tokens processed in/out A / B | cost |", "|---|---|---|---|---|---|---|---|---|"]
    for p in c["configs"]:
        if "pass" not in p:
            out.append(f"| `{p['config_id']}` | no ({'; '.join(p['reasons'])}) | | | | | | | |")
            continue
        out.append(f"| `{p['config_id']}` | {'yes' if p['comparable'] else 'no'} | {' / '.join(p['pass'])} "
                   f"| {p['wilson95'][0]} / {p['wilson95'][1]} | {p['correctness']} | {p['fisher_p']} "
                   f"| {p['pass_duration_median_ms'][0]} / {p['pass_duration_median_ms'][1]} "
                   f"| {p['tokens_processed_in_out'][0]} / {p['tokens_processed_in_out'][1]} | {p['cost']} |")
    out += ["", "Correctness is compared before cost; a difference is claimed only when the Wilson 95% intervals "
            "do not overlap (Fisher p is information only). Durations are wall time on the recording host."]
    return "\n".join(out) + "\n"


def pool(run_dirs, ignore_backend_version=False):
    """Add up runs whose task, graders, executor, backend version and per-config identity equal the first run's."""
    from .report import wilson95
    sides = [_side(r) for r in run_dirs]
    ref = sides[0]
    included, excluded = [], []
    for s in sides:
        reasons = [f"{k} differs" for k in ("task", "graders", "executor") if s[k] != ref[k]]
        if s["versions"] != ref["versions"] and not ignore_backend_version:
            reasons.append("execution backend version differs")
        reasons += [f"config {cid}: {f} differs" for cid in set(s["configs"]) & set(ref["configs"])
                    for f in CONFIG_IDENTITY if s["configs"][cid].get(f) != ref["configs"][cid].get(f)]
        (excluded if reasons else included).append({"run_dir": s["run_dir"], "versions": s["versions"],
                                                     "reasons": reasons, "side": s})
    totals = {}
    for run in included:
        for c in run["side"]["summary"]["configs"]:
            t = totals.setdefault(c["config_id"], {"pass": 0, "started": 0, "graded": 0, "runs": 0})
            t["pass"] += c["operational_success"]["pass"]
            t["started"] += c["operational_success"]["denominator"]
            t["graded"] += c["grades"]["PASS"] + c["grades"]["FAIL"]
            t["runs"] += 1
    for t in totals.values():
        t["wilson95"] = wilson95(t["pass"], t["started"])
    ids = sorted(totals)
    pairs = [{"a": a, "b": b, "fisher_p": fisher_exact(totals[a]["pass"], totals[a]["started"],
                                                     totals[b]["pass"], totals[b]["started"])}
             for i, a in enumerate(ids) for b in ids[i + 1:]]
    return {"task": ref["task"], "ignore_backend_version": ignore_backend_version,
            "included": [{k: r[k] for k in ("run_dir", "versions")} for r in included],
            "excluded": [{k: r[k] for k in ("run_dir", "reasons")} for r in excluded],
            "configs": {cid: totals[cid] for cid in ids}, "pairs": pairs}


def render_pool_markdown(p):
    out = [f"# Pooled runs (task `{p['task']}`)", "",
           f"- included: {len(p['included'])}; excluded: {len(p['excluded'])}"
           + ("; backend versions deliberately ignored" if p["ignore_backend_version"] else ""), ""]
    out += [f"- excluded `{e['run_dir']}`: {'; '.join(e['reasons'])}" for e in p["excluded"]]
    out += ["", "| config | runs | PASS / started | Wilson95 |", "|---|---|---|---|"]
    out += [f"| `{cid}` | {t['runs']} | {t['pass']}/{t['started']} | {t['wilson95']} |" for cid, t in p["configs"].items()]
    out += ["", "| A | B | Fisher exact p (two-sided) |", "|---|---|---|"]
    out += [f"| `{x['a']}` | `{x['b']}` | {x['fisher_p']} |" for x in p["pairs"]]
    return "\n".join(out) + "\n"
