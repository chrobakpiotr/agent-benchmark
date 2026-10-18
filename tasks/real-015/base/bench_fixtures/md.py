"""Task-owned helper for agent-benchmark's hidden cases: mistune imports itself as `mistune`, so put src/ on the path."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import mistune  # noqa: E402


def table_html(text):
    return mistune.create_markdown(plugins=["table"])(text)
