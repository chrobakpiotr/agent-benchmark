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




class RealTask1Bug(unittest.TestCase):
    """real-001-bug v2: symptom-only description; own bundle whose cases use cache_semantics separate (unambiguous)."""

    def test_bundle_and_reference_patches(self):
        bundle = ROOT / "tasks" / "real-001-bug"
        task = validate_task(json.loads((bundle / "task.json").read_text()))
        verify_bundle(task, bundle)
        cases = json.loads((bundle / "hidden" / "cases.json").read_text())["cases"]
        self.assertTrue(all(e["cache_semantics"] == "separate" for c in cases for e in c["args"][0]["usage_events"]))
        for name, want in (("good", "PASS"), ("noop", "FAIL"), ("wrong", "FAIL"), ("overstrict", "FAIL")):
            data = (bundle / "reference" / f"{name}.patch").read_bytes()
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / digest(data).split(":")[1]).write_bytes(data)
                self.assertEqual(grader.grade(task, d, digest(data), bundle_dir=bundle,
                                              host_execution_allowed=True)[0], want, name)

BUNDLE_2 = ROOT / "tasks" / "real-002"
TASK_2 = validate_task(json.loads((BUNDLE_2 / "task.json").read_text()))
FLOATS_AND_BOOL = ["result_applied_bool_for_one", "result_applied_float_limit", "result_applied_float_timeout"]


class RealTask2(unittest.TestCase):
    """real-002: agent-harness fix b29dfdf (two independent v2 validation gaps, one an equality-vs-type trap)."""

    def grade(self, name):
        data = (BUNDLE_2 / "reference" / f"{name}.patch").read_bytes()
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / digest(data).split(":")[1]).write_bytes(data)
            result, criteria = grader.grade(TASK_2, d, digest(data), bundle_dir=BUNDLE_2, host_execution_allowed=True)
        return result, {c["criterion"]: c for c in criteria}

    def test_bundle_matches_pinned_digests(self):
        verify_bundle(TASK_2, BUNDLE_2)

    def test_real_fix_passes(self):
        self.assertEqual(self.grade("good")[0], "PASS")

    def test_base_half_and_overstrict_fixes_fail_on_behaviour(self):
        for name, failed in (("noop", ["request_qualified_without_limits", *FLOATS_AND_BOOL]),
                             ("request_only", FLOATS_AND_BOOL),
                             ("applied_only", ["request_qualified_without_limits"]),
                             ("overstrict", ["request_plain_without_limits", *FLOATS_AND_BOOL])):
            result, c = self.grade(name)
            self.assertEqual((result, c["hidden_cases_pass"]["detail"]["failed"]), ("FAIL", failed), name)

    def test_test_deletion_is_out_of_scope(self):
        result, c = self.grade("test_deletion")
        self.assertEqual((result, c["patch_within_scope"]["detail"]), ("FAIL", ["tests/test_contract_v2.py"]))

    def test_visible_checks_pass_on_base(self):
        p = subprocess.run([sys.executable, "-m", "unittest", "tests.test_contract", "tests.test_contract_v2",
                            "tests.test_boundaries"], cwd=BUNDLE_2 / "base",
                           env={"PATH": "/usr/bin:/bin", "PYTHONPATH": "src", "PYTHONDONTWRITEBYTECODE": "1"},
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr[-500:])

    def test_fake_run_grades_reference_patches(self):
        with tempfile.TemporaryDirectory() as d:
            s = write_report(runner.run(ROOT / "tests" / "fixtures" / "manifest-real-002.json", Path(d) / "run"))
        grades = {c["config_id"]: c["grades"] for c in s["configs"]}
        self.assertEqual(grades["cfg-a"], {"PASS": 1, "FAIL": 1, "INVALID": 0})  # good, request_only
        self.assertEqual(grades["cfg-b"], {"PASS": 0, "FAIL": 2, "INVALID": 0})  # applied_only, noop

    def test_bug_report_variant_shares_the_bundle_and_is_the_task_of_its_run(self):
        variant = BUNDLE_2 / "task-bug-report.json"
        task = validate_task(json.loads(variant.read_text()))
        self.assertEqual((task["task_id"], task["bundle"]), ("real-002-bug", TASK_2["bundle"]))
        self.assertNotIn("float", task["description"])  # only the bool symptom is reported; floats test the fix
        with tempfile.TemporaryDirectory() as d:
            m = json.loads((ROOT / "tests" / "fixtures" / "manifest-real-002.json").read_text())
            m["task"] = {"path": str(variant), "digest": digest(variant.read_bytes())}
            Path(d, "m.json").write_text(json.dumps(m))
            out = runner.run(Path(d, "m.json"), Path(d) / "run")
            s = write_report(out)
            self.assertEqual(json.loads((out / "task" / "task.json").read_text())["task_id"], "real-002-bug")
        self.assertEqual(s["configs"][0]["grades"]["PASS"] + s["configs"][1]["grades"]["PASS"], 1)



class RealTask3(unittest.TestCase):
    """real-003: agent-harness fix b8e1e90, symptom-only; one reference patch per plausible reading."""

    def test_bundle_reference_patches_and_visible_checks(self):
        bundle = ROOT / "tasks" / "real-003"
        task = validate_task(json.loads((bundle / "task.json").read_text()))
        verify_bundle(task, bundle)
        want = {"good": ("PASS", []), "noop": ("FAIL", ["prefix_word", "suffix_digit", "suffix_hyphen_word", "suffix_letter"]),
                "digit_only": ("FAIL", ["prefix_word", "suffix_hyphen_word", "suffix_letter"]),
                "word_boundary": ("FAIL", ["suffix_hyphen_word"]),
                "overstrict": ("FAIL", ["own_job_parenthesised", "own_job_quoted"])}
        for name, (result, failed) in want.items():
            data = (bundle / "reference" / f"{name}.patch").read_bytes()
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / digest(data).split(":")[1]).write_bytes(data)
                r, c = grader.grade(task, d, digest(data), bundle_dir=bundle, host_execution_allowed=True)
            got = next(x["detail"]["failed"] for x in c if x["criterion"] == "hidden_cases_pass")
            self.assertEqual((r, got), (result, failed), name)
        p = subprocess.run([sys.executable, "-m", "unittest", "tests.test_contract", "tests.test_qualification",
                            "tests.test_boundaries"], cwd=bundle / "base",
                           env={"PATH": "/usr/bin:/bin", "PYTHONPATH": "src", "PYTHONDONTWRITEBYTECODE": "1"},
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr[-500:])


class RealTask4(unittest.TestCase):
    """real-004: agent-harness fix 9e01ec4, symptom-only (relabelled report); per-check and review evidence inferred."""

    def test_bundle_reference_patches_and_visible_checks(self):
        bundle = ROOT / "tasks" / "real-004"
        task = validate_task(json.loads((bundle / "task.json").read_text()))
        verify_bundle(task, bundle)
        want = {"good": ("PASS", []),
                "noop": ("FAIL", ["one_check_without_job", "relabelled_job", "stale_review_subject"]),
                "job_only": ("FAIL", ["stale_review_subject"]), "job_any": ("FAIL", ["one_check_without_job"]),
                "overstrict": ("FAIL", ["genuine_json_context"])}
        for name, (result, failed) in want.items():
            data = (bundle / "reference" / f"{name}.patch").read_bytes()
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / digest(data).split(":")[1]).write_bytes(data)
                r, c = grader.grade(task, d, digest(data), bundle_dir=bundle, host_execution_allowed=True)
            got = next(x["detail"]["failed"] for x in c if x["criterion"] == "hidden_cases_pass")
            self.assertEqual((r, got), (result, failed), name)
        p = subprocess.run([sys.executable, "-m", "unittest", "tests.test_contract", "tests.test_qualification",
                            "tests.test_boundaries"], cwd=bundle / "base",
                           env={"PATH": "/usr/bin:/bin", "PYTHONPATH": "src", "PYTHONDONTWRITEBYTECODE": "1"},
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr[-500:])


class RealTask5(unittest.TestCase):
    """real-005: pypa/packaging fix 2aada00, symptom names Requirement only; the SpecifierSet entry point is inferred."""

    def test_bundle_reference_patches_and_visible_check(self):
        bundle = ROOT / "tasks" / "real-005"
        task = validate_task(json.loads((bundle / "task.json").read_text()))
        verify_bundle(task, bundle)
        rejects = ["requirement_empty", "requirement_empty_in_list", "requirement_empty_spaced"]
        sets = ["specifierset_empty", "specifierset_empty_in_list"]
        want = {"good": ("PASS", []), "noop": ("FAIL", rejects + sets), "requirement_only": ("FAIL", sets),
                "overstrict": ("FAIL", ["parse_arbitrary_in_list", "parse_arbitrary_word"])}
        for name, (result, failed) in want.items():
            data = (bundle / "reference" / f"{name}.patch").read_bytes()
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / digest(data).split(":")[1]).write_bytes(data)
                r, c = grader.grade(task, d, digest(data), bundle_dir=bundle, host_execution_allowed=True)
            got = next(x["detail"]["failed"] for x in c if x["criterion"] == "hidden_cases_pass")
            self.assertEqual((r, got), (result, failed), name)
        p = subprocess.run([sys.executable, "-c", "from src.packaging.requirements import Requirement; "
                            "print(Requirement('demo-lib>=1'))"], cwd=bundle / "base",
                           env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "demo-lib>=1"), p.stderr[-300:])

if __name__ == "__main__":
    unittest.main()
