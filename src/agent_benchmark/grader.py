"""Independent grader for the synthetic sort task. Reads only the sealed candidate; never executes it.

Its identity digest is this file's bytes, so any change to grading logic changes the recorded grader digest.
"""
import json
from collections import Counter
from pathlib import Path

from .schema import digest

GRADER_ID = "sort-check"
GRADER_VERSION = "1"
ISOLATION = "none: in-process, data-only candidate, offline fake track (transparent diagnostic, no hidden tests)"


def identity():
    return {"id": GRADER_ID, "version": GRADER_VERSION, "digest": digest(Path(__file__).read_bytes())}


def grade(task, candidates_dir, candidate_digest):
    """Return (result, criteria). INVALID = the candidate cannot be bound to its sealed digest."""
    path = Path(candidates_dir) / candidate_digest.split(":", 1)[-1]
    data = path.read_bytes() if path.is_file() else None
    sealed = data is not None and digest(data) == candidate_digest
    criteria = [{"criterion": "candidate_matches_sealed_digest", "passed": sealed}]
    if not sealed:
        return "INVALID", criteria
    try:
        value = json.loads(data)
    except ValueError:
        value = None
    is_ints = isinstance(value, list) and all(isinstance(v, int) and not isinstance(v, bool) for v in value)
    criteria.append({"criterion": "is_list_of_integers", "passed": is_ints})
    criteria.append({"criterion": "permutation_of_input", "passed": is_ints and Counter(value) == Counter(task["input"])})
    criteria.append({"criterion": "non_decreasing", "passed": is_ints and all(a <= b for a, b in zip(value, value[1:]))})
    return ("PASS" if all(c["passed"] for c in criteria) else "FAIL"), criteria
