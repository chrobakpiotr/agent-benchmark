"""CLI: validate | run | report. Offline only; no model or network calls."""
import argparse
import sys

from . import __version__
from .report import write_report
from .runner import invalidate, plan_trials, resume, run
from .schema import ValidationError, load_manifest


def main(argv=None):
    p = argparse.ArgumentParser(prog="agent-benchmark", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="validate a manifest and its bound task bundle")
    v.add_argument("manifest")
    r = sub.add_parser("run", help="execute a manifest with the FAKE executor and write records + report")
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
    args = p.parse_args(argv)
    try:
        if args.cmd == "validate":
            m = load_manifest(args.manifest)[0]
            print(f"OK {m['experiment_id']}: {len(plan_trials(m))} trials planned, executor={m['executor']['kind']}")
        elif args.cmd == "run":
            out = run(args.manifest, args.out)
            write_report(out)
            print(f"FAKE run written to {out}")
        elif args.cmd == "resume":
            write_report(resume(args.run_dir, replace_unknown=args.replace_unknown))
            print(f"FAKE run resumed in {args.run_dir}")
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
