"""CLI: validate | run | report. Offline only; no model or network calls."""
import argparse
import sys

from . import __version__
from .report import write_report
from .runner import plan_trials, run
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
    args = p.parse_args(argv)
    try:
        if args.cmd == "validate":
            m = load_manifest(args.manifest)[0]
            print(f"OK {m['experiment_id']}: {len(plan_trials(m))} trials planned, executor={m['executor']['kind']}")
        elif args.cmd == "run":
            out = run(args.manifest, args.out)
            write_report(out)
            print(f"FAKE run written to {out}")
        else:
            write_report(args.run_dir)
            print(f"report regenerated in {args.run_dir}")
    except (ValidationError, FileNotFoundError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
