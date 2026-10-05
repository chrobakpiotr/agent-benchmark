"""AB5-05a: deterministic task bundle reference-001 and the patch grader.

Reference patches are authored fixtures, so running them on the host is allowed here. Model-generated patches are
not (see AB5-05b).
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_benchmark import grader, runner  # noqa: E402
from agent_benchmark.report import write_report  # noqa: E402
from agent_benchmark.schema import ValidationError, digest, load_manifest, validate_task, verify_bundle  # noqa: E402

BUNDLE = ROOT / "tasks" / "reference-001"
TASK = validate_task(json.loads((BUNDLE / "task.json").read_text()))
MANIFEST = ROOT / "tests" / "fixtures" / "manifest-reference-001.json"


class PatchGrader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def grade(self, data, task=TASK, bundle=BUNDLE, allowed=True, timeout=None):
        sealed = digest(data)
        (self.root / sealed.split(":")[1]).write_bytes(data)
        result, criteria = grader.grade(task, self.root, sealed, bundle_dir=bundle,
                                        host_execution_allowed=allowed, timeout=timeout)
        return result, {c["criterion"]: c["passed"] for c in criteria}

    def ref(self, name, **kw):
        return self.grade((BUNDLE / "reference" / f"{name}.patch").read_bytes(), **kw)

    def test_bundle_matches_pinned_digests(self):
        verify_bundle(TASK, BUNDLE)

    def test_known_good_passes(self):
        result, c = self.ref("good")
        self.assertEqual(result, "PASS")
        self.assertTrue(c["hidden_test_count_matches"])

    def test_base_noop_wrong_hardcoded_fail_on_behaviour(self):
        for name in ("noop", "wrong", "hardcoded"):
            result, c = self.ref(name)
            self.assertEqual(result, "FAIL", name)
            self.assertTrue(c["patch_applies"], name)
            self.assertFalse(c["hidden_tests_pass"], name)

    def test_test_deletion_and_escape_are_out_of_scope(self):
        for name in ("test_deletion", "escape"):
            result, c = self.ref(name)
            self.assertEqual((result, c["patch_within_scope"]), ("FAIL", False), name)
            self.assertNotIn("patch_applies", c, name)  # never applied
        self.assertFalse((Path(tempfile.gettempdir()) / "escape.txt").exists())

    def test_import_hijack_and_hidden_test_edit_are_out_of_scope(self):
        good = (BUNDLE / "reference" / "good.patch").read_text()
        for target in ("b/sitecustomize.py", "b/../hidden/test_hidden.py", "/etc/passwd", "b/tests/test_visible.py"):
            result, c = self.grade((good + f"--- /dev/null\n+++ {target}\n@@ -0,0 +1 @@\n+x\n").encode())
            self.assertEqual((result, c["patch_within_scope"]), ("FAIL", False), target)

    def test_wrong_base_and_malformed_do_not_apply(self):
        for name in ("bad_base", "malformed"):
            result, c = self.ref(name)
            self.assertEqual((result, c["patch_applies"]), ("FAIL", False), name)

    def test_hanging_candidate_is_killed(self):
        result, c = self.ref("hang", timeout=1)
        self.assertEqual((result, c["hidden_tests_finished_within_limit"]), ("FAIL", False))

    def test_tampered_bundle_is_invalid(self):
        for part, rel in (("hidden", "hidden/test_hidden.py"), ("base", "base/tests/test_visible.py")):
            copy = self.root / f"bundle-{part}"
            shutil.copytree(BUNDLE, copy)
            (copy / rel).write_text("import unittest\n")
            result, c = self.ref("good", bundle=copy)
            self.assertEqual((result, c["bundle_matches_pinned_digests"]), ("INVALID", False), part)

    def test_hidden_test_multiplicity_is_enforced(self):
        task = json.loads(json.dumps(TASK))
        task["bundle"]["hidden_test_count"] = 5
        result, c = self.ref("good", task=task)
        self.assertEqual((result, c["hidden_test_count_matches"], c["hidden_tests_pass"]), ("FAIL", False, True))

    def test_host_execution_needs_vouched_source(self):
        result, c = self.ref("good", allowed=False)
        self.assertEqual((result, c["host_execution_allowed"]), ("INVALID", False))

    def test_patch_paths_parser(self):
        git_style = ("diff --git a/calc.py b/other.py\nsimilarity index 90%\nrename from calc.py\nrename to other.py\n")
        self.assertEqual(grader.patch_paths(git_style), {"calc.py", "other.py"})
        self.assertEqual(grader.patch_paths("--- a/calc.py\t2026-10-05\n+++ b/calc.py\t2026-10-05\n"), {"calc.py"})

    def test_symlink_mode_is_rejected(self):
        patch = "diff --git a/calc.py b/calc.py\nnew file mode 120000\n--- /dev/null\n+++ b/calc.py\n@@ -0,0 +1 @@\n+/etc\n"
        self.assertEqual(self.grade(patch.encode())[0], "FAIL")


class ReferencePipeline(unittest.TestCase):
    def test_fake_run_grades_reference_patches(self):
        with tempfile.TemporaryDirectory() as d:
            s = write_report(runner.run(MANIFEST, Path(d) / "run"))
        grades = {c["config_id"]: c["grades"] for c in s["configs"]}
        # cfg-a: good PASS, hardcoded FAIL; cfg-b: wrong FAIL, test_deletion FAIL
        self.assertEqual(grades["cfg-a"], {"PASS": 1, "FAIL": 1, "INVALID": 0})
        self.assertEqual(grades["cfg-b"], {"PASS": 0, "FAIL": 2, "INVALID": 0})
        self.assertEqual([g["id"] for g in s["graders"]], ["patch-unittest"])
        self.assertEqual(sum(c["completion_accepted_not_pass"] for c in s["configs"]), 3)

    def test_unknown_reference_candidate_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            m = json.loads(MANIFEST.read_text())
            m["executor"]["script"][0]["candidate"] = "nonexistent"
            m["task"]["path"] = str(BUNDLE / "task.json")
            Path(d, "m.json").write_text(json.dumps(m))
            with self.assertRaisesRegex(ValidationError, "not available"):
                load_manifest(Path(d) / "m.json")


if __name__ == "__main__":
    unittest.main()
