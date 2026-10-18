"""Task-owned helper for agent-benchmark's hidden cases: mistune imports itself as `mistune`, so put src/ on the path."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mistune import html  # noqa: E402,F401
