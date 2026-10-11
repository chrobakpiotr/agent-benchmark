"""CLI: validate | run | report | resume | invalidate | preflight | compare. Offline only; no model or network calls."""
import argparse
import sys
from pathlib import Path

from . import __version__, compare, zero_spend
from .report import write_report
from .runner import invalidate, plan_trials, resume, run
from .schema import ValidationError, load_manifest


def main(argv=None):
    p = argparse.ArgumentParser(prog="agent-benchmark", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="validate a manifest and its bound task bundle")
    v.add_argument("manifest")
    r = sub.add_parser("run", help="execute a manifest (fake executor, or real agent CLIs) and write records + report")
    r.add_argument("manifest")
    r.add_argument("--out", required=True, help="new run directory (must not exist)")
    rep = sub.add_parser("report", help="regenerate report.md/report.csv/summary.json from recorded events only")
    rep.add_argument("run_dir")
    rep.add_argument("--pricing", help="dated pricing snapshot JSON; bound to the run on first use")
    res = sub.add_parser("resume", help="continue an interrupted run; started-but-unfinished trials become 'unknown'")
    res.add_argument("run_dir")
    res.add_argument("--replace-unknown", action="store_true",
                     help="add a replacement trial (new identity, linked via 'replaces') for each reconciled one")
    inv = sub.add_parser("invalidate", help="append a correction record that invalidates one trial's grade")
    inv.add_argument("run_dir")
    inv.add_argument("trial_id")
    inv.add_argument("--reason", required=True)
    cmp = sub.add_parser("compare", help="compare two recorded runs; says first whether they are comparable")
    cmp.add_argument("run_a")
    cmp.add_argument("run_b")
    cmp.add_argument("--out", help="also write the Markdown comparison to this file")
    po = sub.add_parser("pool", help="add up comparable runs per config (refuses mismatched runs unless told)")
    po.add_argument("run_dirs", nargs="+")
    po.add_argument("--ignore-backend-version", action="store_true", help="pool across harness versions (reported)")
    po.add_argument("--out", help="write the Markdown here instead of stdout")
    sub.add_parser("preflight", help="check zero-spend preconditions: no API-billing env vars, subscription logins")
    args = p.parse_args(argv)
    if args.cmd == "preflight":
        found = zero_spend.problems()
        for line in found:
            print(f"FAIL {line}", file=sys.stderr)
        print("OK zero-spend preconditions hold" if not found else f"{len(found)} problem(s)")
        return 1 if found else 0
    try:
        if args.cmd == "validate":
            m = load_manifest(args.manifest)[0]
            print(f"OK {m['experiment_id']}: {len(plan_trials(m))} trials planned, executor={m['executor']['kind']}")
        elif args.cmd == "run":
            out = run(args.manifest, args.out)
            s = write_report(out)
            print(f"{'FAKE' if s['fake_execution'] else 'REAL agent-cli'} run written to {out}")
        elif args.cmd == "resume":
            s = write_report(resume(args.run_dir, replace_unknown=args.replace_unknown))
            print(f"{'FAKE' if s['fake_execution'] else 'REAL agent-cli'} run resumed in {args.run_dir}")
        elif args.cmd == "compare":
            md = compare.render_markdown(compare.compare(args.run_a, args.run_b))
            if args.out:
                Path(args.out).write_text(md, encoding="utf-8")
            print(md, end="")
        elif args.cmd == "pool":
            md = compare.render_pool_markdown(compare.pool(args.run_dirs, args.ignore_backend_version))
            if args.out:
                Path(args.out).write_text(md, encoding="utf-8")
            print(md, end="")
        elif args.cmd == "invalidate":
            invalidate(args.run_dir, args.trial_id, args.reason)
            write_report(args.run_dir)
            print(f"correction recorded for {args.trial_id}")
        else:
            write_report(args.run_dir, args.pricing)
            print(f"report regenerated in {args.run_dir}")
    except (ValidationError, FileNotFoundError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
