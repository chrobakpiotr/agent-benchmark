"""Task-owned helper for agent-benchmark's hidden cases: codex exec JSON events in, the usage report as JSON out."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_harness import execution  # noqa: E402


def report(events):
    return list(execution._codex_report("\n".join(json.dumps(e) for e in events).encode()))
