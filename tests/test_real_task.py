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
    """real-001-bug v3: symptom-only description; cases use cache_semantics separate, and both readings of a missing
    summary (upstream: complete needs one; stream fallback: the streams are the usage) pass."""

    def test_bundle_and_reference_patches(self):
        bundle = ROOT / "tasks" / "real-001-bug"
        task = validate_task(json.loads((bundle / "task.json").read_text()))
        verify_bundle(task, bundle)
        cases = json.loads((bundle / "hidden" / "cases.json").read_text())["cases"]
        self.assertTrue(all(e["cache_semantics"] == "separate" for c in cases for e in c["args"][0]["usage_events"]))
        override = "complete_summary_overrides_null_stream"
        for name, want in (("good", []), ("stream_fallback", []),
                           ("noop", ["complete_null_cache_read", "complete_null_input",
                                     "complete_stream_only_null_cache_read"]),
                           ("wrong", [override]), ("overstrict", [override, "partial_null_units_valid"])):
            data = (bundle / "reference" / f"{name}.patch").read_bytes()
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / digest(data).split(":")[1]).write_bytes(data)
                result, criteria = grader.grade(task, d, digest(data), bundle_dir=bundle, host_execution_allowed=True)
            failed = {c["criterion"]: c for c in criteria}["hidden_cases_pass"].get("detail", {}).get("failed", [])
            self.assertEqual((result, failed), ("FAIL" if want else "PASS", want), name)

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
                "every_file_target_and_job": ("FAIL", ["stale_review_subject"]),
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


class RealTask6(unittest.TestCase):
    """real-006: pypa/packaging fix d3e7f5d; the report names a float, a list fails through another exception path."""

    def test_bundle_reference_patches_and_visible_check(self):
        bundle = ROOT / "tasks" / "real-006"
        task = validate_task(json.loads((bundle / "task.json").read_text()))
        verify_bundle(task, bundle)
        non_float = ["dict", "int", "list_of_str", "list_two_parts", "none"]
        want = {"good": ("PASS", []), "noop": ("FAIL", sorted(non_float + ["float_reported"])),
                "float_only": ("FAIL", non_float), "catch_typeerror": ("FAIL", ["list_of_str", "list_two_parts"]),
                "coerce_to_str": ("FAIL", ["float_reported", "int"])}
        for name, (result, failed) in want.items():
            data = (bundle / "reference" / f"{name}.patch").read_bytes()
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / digest(data).split(":")[1]).write_bytes(data)
                r, c = grader.grade(task, d, digest(data), bundle_dir=bundle, host_execution_allowed=True)
            got = next(x["detail"]["failed"] for x in c if x["criterion"] == "hidden_cases_pass")
            self.assertEqual((r, got), (result, failed), name)
        p = subprocess.run([sys.executable, "-c", "from src.packaging.version import Version; print(Version('1.0rc1'))"],
                           cwd=bundle / "base", env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
                           capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "1.0rc1"), p.stderr[-300:])


class RealTask7(unittest.TestCase):
    """real-007: pypa/packaging fix f14a093; the report shows the post group only, the pre group is inferred."""

    def test_bundle_reference_patches_and_visible_check(self):
        bundle = ROOT / "tasks" / "real-007"
        task = validate_task(json.loads((bundle / "task.json").read_text()))
        verify_bundle(task, bundle)
        pre = ["pre_dotless_i", "pre_dotted_capital_i"]
        want = {"good": ("PASS", []), "ascii_flag_global": ("PASS", []),
                "noop": ("FAIL", ["post_long_s_in_set", "post_long_s_reported", "post_long_s_requirement"] + pre),
                "post_only": ("FAIL", pre), "no_ignorecase": ("FAIL", ["valid_upper_dev", "valid_upper_rc"])}
        for name, (result, failed) in want.items():
            data = (bundle / "reference" / f"{name}.patch").read_bytes()
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / digest(data).split(":")[1]).write_bytes(data)
                r, c = grader.grade(task, d, digest(data), bundle_dir=bundle, host_execution_allowed=True)
            got = next(x["detail"]["failed"] for x in c if x["criterion"] == "hidden_cases_pass")
            self.assertEqual((r, got), (result, failed), name)
        p = subprocess.run([sys.executable, "-c", "from src.packaging.specifiers import SpecifierSet; "
                            "print(SpecifierSet('~=1.0.post1'))"], cwd=bundle / "base",
                           env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "~=1.0.post1"), p.stderr[-300:])


class RealTask8(unittest.TestCase):
    """real-008: python-semver fix 1d51591; the report shows a crash, SemVer ordering of long identifiers is inferred."""

    def test_bundle_reference_patches_and_visible_check(self):
        bundle = ROOT / "tasks" / "real-008"
        task = validate_task(json.loads((bundle / "task.json").read_text()))
        verify_bundle(task, bundle)
        long = ["long_equal", "long_magnitude_by_length", "long_numeric_below_alphanumeric", "long_vs_short_reported",
                "long_vs_short_reversed"]
        want = {"good": ("PASS", []), "int_limit_off": ("PASS", []), "noop": ("FAIL", long),
                "catch_as_string": ("FAIL", ["long_magnitude_by_length"]),
                "lexicographic_digits": ("FAIL", ["guard_short_numeric", "long_magnitude_by_length"]),
                "reject_long": ("FAIL", long)}
        for name, (result, failed) in want.items():
            data = (bundle / "reference" / f"{name}.patch").read_bytes()
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / digest(data).split(":")[1]).write_bytes(data)
                r, c = grader.grade(task, d, digest(data), bundle_dir=bundle, host_execution_allowed=True)
            got = next(x["detail"]["failed"] for x in c if x["criterion"] == "hidden_cases_pass")
            self.assertEqual((r, got), (result, failed), name)
        p = subprocess.run([sys.executable, "-W", "ignore", "-c", "import src.semver as s; "
                            "print(s.compare('1.0.0-alpha.2', '1.0.0-alpha.10'))"], cwd=bundle / "base",
                           env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "-1"), p.stderr[-300:])


class RealTask9(unittest.TestCase):
    """real-009: python-semver fix 0aa17a3; the report shows == crashing, Python's operand rule for the rest is inferred."""

    def test_bundle_reference_patches_and_visible_check(self):
        bundle = ROOT / "tasks" / "real-009"
        task = validate_task(json.loads((bundle / "task.json").read_text()))
        verify_bundle(task, bundle)
        eq_ne = ["eq_empty_dict_reported", "eq_unknown_key", "ne_empty_dict", "ne_unknown_key"]
        want = {"good": ("PASS", []), "notimplemented_on_typeerror": ("PASS", []), "noop": ("FAIL", eq_ne),
                "catch_return_false": ("FAIL", ["gt_unknown_key", "lt_empty_dict", "ne_empty_dict", "ne_unknown_key"]),
                "raise_typeerror": ("FAIL", eq_ne)}
        for name, (result, failed) in want.items():
            data = (bundle / "reference" / f"{name}.patch").read_bytes()
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / digest(data).split(":")[1]).write_bytes(data)
                r, c = grader.grade(task, d, digest(data), bundle_dir=bundle, host_execution_allowed=True)
            got = next(x["detail"]["failed"] for x in c if x["criterion"] == "hidden_cases_pass")
            self.assertEqual((r, got), (result, failed), name)
        p = subprocess.run([sys.executable, "-W", "ignore", "-c", "from src.semver import Version; "
                            "print(Version.parse('1.2.3') < (2, 0, 0))"], cwd=bundle / "base",
                           env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "True"), p.stderr[-300:])


class RealTask10(unittest.TestCase):
    """real-010: python-humanize fix 823ad60; the report shows the default format, format-dependent rollover is inferred."""

    def test_bundle_reference_patches_and_visible_check(self):
        bundle = ROOT / "tasks" / "real-010"
        task = validate_task(json.loads((bundle / "task.json").read_text()))
        verify_bundle(task, bundle)
        want = {"good": ("PASS", []),
                "noop": ("FAIL", ["binary", "default_edge", "default_reported", "format_no_decimals",
                                  "format_two_decimals", "gnu", "negative"]),
                "threshold_default": ("FAIL", ["format_no_decimals", "guard_binary_below", "guard_more_precision"]),
                "round_one_decimal": ("FAIL", ["format_no_decimals", "guard_more_precision"])}
        for name, (result, failed) in want.items():
            data = (bundle / "reference" / f"{name}.patch").read_bytes()
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / digest(data).split(":")[1]).write_bytes(data)
                r, c = grader.grade(task, d, digest(data), bundle_dir=bundle, host_execution_allowed=True)
            got = next(x["detail"]["failed"] for x in c if x["criterion"] == "hidden_cases_pass")
            self.assertEqual((r, got), (result, failed), name)
        p = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'src'); import humanize; "
                            "print(humanize.naturalsize(1500))"], cwd=bundle / "base",
                           env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "1.5 kB"), p.stderr[-300:])


class RealTask11(unittest.TestCase):
    """real-011: croniter fix f64665e; other fields and croniter's deliberate whole-cycle equal range are inferred."""

    def test_bundle_reference_patches_and_visible_check(self):
        bundle = ROOT / "tasks" / "real-011"
        task = validate_task(json.loads((bundle / "task.json").read_text()))
        verify_bundle(task, bundle)
        want = {"good": ("PASS", []),
                "noop": ("FAIL", ["day_of_month_max", "day_of_week_max", "hour_max", "minute_max_reported", "month_max"]),
                "equal_range_single": ("FAIL", ["guard_explicit_equal_range", "guard_explicit_equal_range_step"]),
                "equal_range_with_step": ("FAIL", ["guard_explicit_equal_range_step"])}
        for name, (result, failed) in want.items():
            data = (bundle / "reference" / f"{name}.patch").read_bytes()
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / digest(data).split(":")[1]).write_bytes(data)
                r, c = grader.grade(task, d, digest(data), bundle_dir=bundle, host_execution_allowed=True)
            got = next(x["detail"]["failed"] for x in c if x["criterion"] == "hidden_cases_pass")
            self.assertEqual((r, got), (result, failed), name)
        p = subprocess.run([sys.executable, "-W", "ignore", "-c", "from datetime import datetime; from croniter import "
                            "croniter; print(croniter('*/20 * * * *', datetime(2026, 1, 1)).get_next(datetime))"],
                           cwd=bundle / "base", env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
                                                     "PYTHONPATH": "bench_fixtures/vendor:src"},
                           capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "2026-01-01 00:20:00"), p.stderr[-300:])



class RealTask12(unittest.TestCase):
    """real-012: Python-Markdown fix 7c265bc; other unterminated end-tag shapes (also outside code) are inferred."""

    def test_bundle_reference_patches_and_visible_checks(self):
        bundle = ROOT / "tasks" / "real-012"
        task = validate_task(json.loads((bundle / "task.json").read_text()))
        verify_bundle(task, bundle)
        want = {"good": ("PASS", []),
                "noop": ("FAIL", ["code_span_later_gt", "code_span_path_reported", "code_span_space_in_name",
                                  "code_span_trailing_slash", "plain_text_unterminated"]),
                "slash_path_only": ("FAIL", ["code_span_later_gt", "code_span_space_in_name", "plain_text_unterminated"]),
                "gt_lookahead": ("FAIL", ["code_span_later_gt", "code_span_trailing_slash"])}
        for name, (result, failed) in want.items():
            data = (bundle / "reference" / f"{name}.patch").read_bytes()
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / digest(data).split(":")[1]).write_bytes(data)
                r, c = grader.grade(task, d, digest(data), bundle_dir=bundle, host_execution_allowed=True)
            got = next(x["detail"]["failed"] for x in c if x["criterion"] == "hidden_cases_pass")
            self.assertEqual((r, got), (result, failed), name)
        p = subprocess.run([sys.executable, "-m", "unittest", "tests.test_syntax.blocks.test_html_blocks",
                            "tests.test_syntax.inline.test_code"], cwd=bundle / "base",
                           env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr[-500:])


class RealTask13(unittest.TestCase):
    """real-013: mistune fix 2d26bc8; the CommonMark multiple-of-3 rule on both sides of a partially consumed run."""

    def test_bundle_reference_patches_and_visible_checks(self):
        bundle = ROOT / "tasks" / "real-013"
        task = validate_task(json.loads((bundle / "task.json").read_text()))
        verify_bundle(task, bundle)
        opener = ["double_opener_single_closer", "in_sentence", "opener_run_consumed_first", "opener_run_triple",
                  "reported_shape_other_text", "strong_closer_remainder", "underscore_content"]
        closer = ["closer_run_consumed_first", "closer_run_triple"]
        want = {"good": ("PASS", []), "noop": ("FAIL", sorted(opener + closer)), "closer_only": ("FAIL", opener),
                "opener_only": ("FAIL", closer),
                "no_rule": ("FAIL", ["closer_run_consumed_first", "double_opener_single_closer", "guard_spec_rule_9"])}
        for name, (result, failed) in want.items():
            data = (bundle / "reference" / f"{name}.patch").read_bytes()
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / digest(data).split(":")[1]).write_bytes(data)
                r, c = grader.grade(task, d, digest(data), bundle_dir=bundle, host_execution_allowed=True)
            got = next(x["detail"]["failed"] for x in c if x["criterion"] == "hidden_cases_pass")
            self.assertEqual((r, got), (result, failed), name)
        p = subprocess.run([sys.executable, "-m", "unittest", "tests.test_commonmark", "tests.test_syntax"],
                           cwd=bundle / "base", capture_output=True, text=True,
                           env={"PATH": "/usr/bin:/bin", "PYTHONPATH": "src", "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(p.returncode, 0, p.stderr[-500:])


class BundlesAreTracked(unittest.TestCase):
    def test_no_bundle_file_is_hidden_by_a_gitignore(self):
        """A bundle's own .gitignore (e.g. src/*/_version.py) must not keep a needed file out of the repository:
        the digest would then differ in a fresh checkout (CI) although it matches locally."""
        p = subprocess.run(["git", "ls-files", "--others", "--ignored", "--exclude-standard", "tasks"], cwd=ROOT,
                           capture_output=True, text=True)
        if p.returncode != 0:
            self.skipTest("not a git checkout")
        hidden = [f for f in p.stdout.splitlines() if "__pycache__" not in f and not f.endswith(".pyc")]
        self.assertEqual(hidden, [], "add them with git add -f")

    def test_every_bundle_matches_its_pinned_digests(self):
        """Task bases are frozen snapshots of upstream trees (some contain agent-harness source); they are inputs,
        never the runtime dependency, and must not change without a new task version and digest."""
        for path in sorted((ROOT / "tasks").glob("*/task*.json")):
            task = validate_task(json.loads(path.read_text()))
            verify_bundle(task, path.parent)

if __name__ == "__main__":
    unittest.main()
