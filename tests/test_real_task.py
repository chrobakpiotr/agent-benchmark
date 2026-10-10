"""AB5-05a real task real-001: agent-harness fix 2ada5ff graded by patch-io.

Reference patches are authored fixtures (the real fix and known-bad variants), so running them on the host is
allowed here. Model-generated patches are not (see AB5-05b).
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_benchmark import grader, runner  # noqa: E402
from agent_benchmark.report import write_report  # noqa: E402
from agent_benchmark.schema import digest, validate_task, verify_bundle  # noqa: E402

BUNDLE = ROOT / "tasks" / "real-001"
TASK = validate_task(json.loads((BUNDLE / "task.json").read_text()))
MANIFEST = ROOT / "tests" / "fixtures" / "manifest-real-001.json"
BUG_CASES = ["complete_null_cache_read", "complete_null_input", "complete_without_summary"]


class RealTask(unittest.TestCase):
    def grade(self, name):
        data = (BUNDLE / "reference" / f"{name}.patch").read_bytes()
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / digest(data).split(":")[1]).write_bytes(data)
            result, criteria = grader.grade(TASK, d, digest(data), bundle_dir=BUNDLE, host_execution_allowed=True)
        return result, {c["criterion"]: c for c in criteria}

    def test_bundle_matches_pinned_digests(self):
        verify_bundle(TASK, BUNDLE)

    def test_real_fix_passes(self):
        result, c = self.grade("good")
        self.assertEqual(result, "PASS")
        self.assertTrue(c["hidden_case_count_matches"]["passed"])

    def test_base_and_partial_or_overstrict_fixes_fail_on_behaviour(self):
        for name, failed in (("noop", BUG_CASES), ("wrong", ["complete_without_summary"]),
                             ("overstrict", ["complete_without_summary", "partial_null_units_valid"])):
            result, c = self.grade(name)
            self.assertEqual((result, c["hidden_cases_pass"]["detail"]["failed"]), ("FAIL", failed), name)

    def test_test_deletion_is_out_of_scope(self):
        result, c = self.grade("test_deletion")
        self.assertEqual((result, c["patch_within_scope"]["detail"]), ("FAIL", ["tests/test_contract.py"]))

    def test_visible_checks_pass_on_base(self):
        # the bundle is a complete workspace: the task's visible checks run as stated
        p = subprocess.run([sys.executable, "-m", "unittest", "tests.test_contract", "tests.test_boundaries"],
                           cwd=BUNDLE / "base", env={"PATH": "/usr/bin:/bin", "PYTHONPATH": "src",
                                                     "PYTHONDONTWRITEBYTECODE": "1"},
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr[-500:])

    def test_fake_run_grades_reference_patches(self):
        with tempfile.TemporaryDirectory() as d:
            s = write_report(runner.run(MANIFEST, Path(d) / "run"))
        grades = {c["config_id"]: c["grades"] for c in s["configs"]}
        self.assertEqual(grades["cfg-a"], {"PASS": 1, "FAIL": 1, "INVALID": 0})  # good, wrong
        self.assertEqual(grades["cfg-b"], {"PASS": 0, "FAIL": 2, "INVALID": 0})  # overstrict, noop


if __name__ == "__main__":
    unittest.main()
