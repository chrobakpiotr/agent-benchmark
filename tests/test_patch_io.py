"""AB5-05b benchmark side: patch-io grader, verdict computed outside the candidate's process (task reference-002).

Reference patches are authored fixtures, so running them on the host is allowed here (transparent diagnostic).
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_benchmark import grader, runner  # noqa: E402
from agent_benchmark.report import write_report  # noqa: E402
from agent_benchmark.schema import digest, validate_task, verify_bundle  # noqa: E402

BUNDLE = ROOT / "tasks" / "reference-002"
TASK = validate_task(json.loads((BUNDLE / "task.json").read_text()))
MANIFEST = ROOT / "tests" / "fixtures" / "manifest-reference-002.json"
BASE = (BUNDLE / "base" / "calc.py").read_text().splitlines()
GOOD = '''def median(values):
    if not values:
        raise ValueError("median of empty sequence")
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2
'''
CANARY = "sk-canary-2f9e41"


def rewrite(source):
    """Patch replacing the whole base calc.py with `source`."""
    new = source.splitlines()
    return "\n".join(["--- a/calc.py", "+++ b/calc.py", f"@@ -1,{len(BASE)} +1,{len(new)} @@",
                      *("-" + line for line in BASE), *("+" + line for line in new)]).encode() + b"\n"


class PatchIO(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def grade(self, data, bundle=BUNDLE, timeout=None):
        sealed = digest(data)
        (self.root / sealed.split(":")[1]).write_bytes(data)
        result, criteria = grader.grade(TASK, self.root, sealed, bundle_dir=bundle, host_execution_allowed=True,
                                        timeout=timeout)
        return result, {c["criterion"]: c["passed"] for c in criteria}

    def ref(self, name, **kw):
        return self.grade((BUNDLE / "reference" / f"{name}.patch").read_bytes(), **kw)

    def test_bundle_matches_pinned_digests(self):
        verify_bundle(TASK, BUNDLE)

    def test_known_good_passes(self):
        self.assertEqual(self.ref("good"), ("PASS", {
            "candidate_matches_sealed_digest": True, "bundle_matches_pinned_digests": True,
            "patch_within_scope": True, "patch_applies": True, "hidden_cases_finished_within_limit": True,
            "output_file_valid": True, "hidden_case_count_matches": True, "hidden_cases_pass": True}))
        self.assertEqual(self.grade(rewrite(GOOD))[0], "PASS")

    def test_noop_wrong_hardcoded_fail_on_behaviour(self):
        for name in ("noop", "wrong", "hardcoded"):
            result, c = self.ref(name)
            self.assertEqual((result, c["output_file_valid"], c["hidden_cases_pass"]), ("FAIL", True, False), name)

    def test_scope_and_hang(self):
        for name in ("test_deletion", "escape"):
            self.assertEqual(self.ref(name)[1]["patch_within_scope"], False, name)
        result, c = self.ref("hang", timeout=1)
        self.assertEqual((result, c["hidden_cases_finished_within_limit"]), ("FAIL", False))

    def test_forged_test_report_is_fail(self):
        # passes patch-unittest (prints its success line, exits 0 at import); here exit code and output are evidence
        forge = 'import os, sys\nsys.stderr.write("Ran 4 tests\\n\\nOK\\n")\nos._exit(0)\n' + GOOD
        result, c = self.grade(rewrite(forge))
        self.assertEqual((result, c["hidden_cases_finished_within_limit"], c["output_file_valid"]),
                         ("FAIL", True, False))

    def test_forged_output_file_needs_the_right_values(self):
        answers = {cid: {"value": 1} for cid in ("unsorted_odd", "unsorted_even", "single", "empty_raises")}
        forge = f"import json, os, sys\njson.dump({answers!r}, open(sys.argv[2], 'w'))\nos._exit(0)\n" + GOOD
        result, c = self.grade(rewrite(forge))
        self.assertEqual((result, c["output_file_valid"], c["hidden_cases_pass"]), ("FAIL", True, False))

    def test_expected_values_never_reach_the_candidate(self):
        # correct median, unless anything near the candidate process holds expected values or names them
        # 2.5 occurs only among the expected values; needles are assembled at run time so the probe's own source
        # (calc.py, candidate.patch) does not match
        probe = ("import pathlib\n"
                 "_LEAK = any('expect' + 'ed' in p.name or (p.is_file() and b'2.' + b'5' in p.read_bytes())\n"
                 "            for p in pathlib.Path.cwd().parent.rglob('*'))\n")
        source = probe + GOOD.replace("    if not values:", "    if _LEAK or not values:")
        self.assertEqual(self.grade(rewrite(source))[0], "PASS")

    def test_symlinked_or_oversized_output_is_refused(self):
        right = {"unsorted_odd": {"value": 5}, "unsorted_even": {"value": 2.5}, "single": {"value": 7},
                 "empty_raises": {"raises": ["ValueError"]}}
        link = (f"import json, os, sys\nsrc = os.path.join(os.path.dirname(sys.argv[2]), 'elsewhere.json')\n"
                f"json.dump({right!r}, open(src, 'w'))\nos.symlink(src, sys.argv[2])\nos._exit(0)\n")
        big = "import os, sys\nopen(sys.argv[2], 'w').write('{\"x\": \"' + 'a' * (2 << 20) + '\"}')\nos._exit(0)\n"
        for source in (link, big):
            result, c = self.grade(rewrite(source + GOOD))
            self.assertEqual((result, c["output_file_valid"]), ("FAIL", False))

    def test_tampered_bundle_is_invalid(self):
        for part, name in (("expected", "expected.json"), ("hidden", "cases.json")):
            copy = self.root / f"bundle-{part}"
            shutil.copytree(BUNDLE, copy)
            (copy / part / name).write_text((copy / part / name).read_text().replace("7", "8"))
            self.assertEqual(self.ref("good", bundle=copy)[0], "INVALID", part)

    def test_candidate_runs_without_the_callers_secrets(self):
        source = GOOD.replace("    if not values:", '    if not values or "BENCH_CANARY_KEY" in __import__("os").environ:')
        with mock.patch.dict(os.environ, {"BENCH_CANARY_KEY": CANARY}):
            self.assertEqual(self.grade(rewrite(source))[0], "PASS")


class PatchIOPipeline(unittest.TestCase):
    def test_fake_run_grades_reference_patches(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"BENCH_CANARY_KEY": CANARY}):
            out = runner.run(MANIFEST, Path(d) / "run")
            s = write_report(out)
            leaks = [p for p in out.rglob("*") if p.is_file() and CANARY.encode() in p.read_bytes()]
        grades = {c["config_id"]: c["grades"] for c in s["configs"]}
        # cfg-a: good PASS, hardcoded FAIL; cfg-b: wrong FAIL, test_deletion FAIL
        self.assertEqual(grades["cfg-a"], {"PASS": 1, "FAIL": 1, "INVALID": 0})
        self.assertEqual(grades["cfg-b"], {"PASS": 0, "FAIL": 2, "INVALID": 0})
        self.assertEqual([g["id"] for g in s["graders"]], ["patch-io"])
        self.assertEqual(leaks, [])


if __name__ == "__main__":
    unittest.main()
