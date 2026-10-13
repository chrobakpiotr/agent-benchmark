"""Task-owned helper for agent-benchmark's hidden cases: humanize imports itself as `humanize`, so put src/ on the path."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from humanize.filesize import naturalsize  # noqa: E402,F401
