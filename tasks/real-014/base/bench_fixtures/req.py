"""Task-owned helper for agent-benchmark's hidden cases: a parsed requirement as JSON-serializable fields."""
from src.packaging.requirements import Requirement


def req(text):
    r = Requirement(text)
    return [r.name, r.url, sorted(r.extras), str(r.specifier), None if r.marker is None else str(r.marker)]
