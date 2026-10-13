"""Task-owned helper for agent-benchmark's hidden cases: put the vendored dependencies and src/ on the path, then
return croniter results as plain data (ISO timestamps, expanded field lists)."""
import sys
from datetime import datetime
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_root / "bench_fixtures" / "vendor"), str(_root / "src")]

from croniter import croniter  # noqa: E402


def next_runs(expr, start, n=3):
    it = croniter(expr, datetime.fromisoformat(start))
    return [it.get_next(datetime).isoformat() for _ in range(n)]


def expand(expr):
    return croniter.expand(expr)[0]
