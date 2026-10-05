"""AB5-02: offline vertical slice manifest -> fake run -> grade -> report, checked against hand-computed counts."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_benchmark import grader, runner  # noqa: E402
from agent_benchmark.report import load_run, summarize, wilson95, write_report  # noqa: E402
from agent_benchmark.schema import canonical, digest  # noqa: E402

MANIFEST = Path(__file__).parent / "fixtures" / "manifest-offline-001.json"
TASK = {"input": [3, 1, 2, 3, -5]}

# Hand-computed from the fixture script (see docs/specs/ab5-offline-mvp/spec.md, "Oracle"):
# cfg-a: good PASS, good PASS, noop FAIL (harness claimed success)  -> 2/3
# cfg-b: good PASS, timeout ungraded, error ungraded                 -> 1/3
EXPECTED = {
    "cfg-a": {"started": 3, "outcomes": {"completed": 3, "timeout": 0, "cancel": 0, "error": 0, "unknown": 0},
              "grades": {"PASS": 2, "FAIL": 1, "INVALID": 0}, "ungraded": 0, "harness_success_not_pass": 1,
              "wilson95": [0.2077, 0.9385], "coverage": {"complete": 1, "partial": 1, "unknown": 1},
              "known_subtotal": {"input_tokens": 150, "output_tokens": 20, "cache_read_tokens": 0}},
    "cfg-b": {"started": 3, "outcomes": {"completed": 1, "timeout": 1, "cancel": 0, "error": 1, "unknown": 0},
              "grades": {"PASS": 1, "FAIL": 0, "INVALID": 0}, "ungraded": 2, "harness_success_not_pass": 0,
              "wilson95": [0.0615, 0.7923], "coverage": {"complete": 1, "partial": 0, "unknown": 2},
              "known_subtotal": {"input_tokens": 200, "output_tokens": 40, "cache_read_tokens": 0}},
}


class OfflinePipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "run"
        runner.run(MANIFEST, self.out)
        self.summary = write_report(self.out)

    def tearDown(self):
        self.tmp.cleanup()

    def test_counts_match_hand_computed_oracle(self):
        for c in self.summary["configs"]:
            e = EXPECTED[c["config_id"]]
            self.assertEqual(c["started"], e["started"])
            self.assertEqual(c["outcomes"], e["outcomes"])
            self.assertEqual(c["grades"], e["grades"])
            self.assertEqual(c["ungraded"], e["ungraded"])
            self.assertEqual(c["harness_success_not_pass"], e["harness_success_not_pass"])
            self.assertEqual(c["operational_success"]["wilson95"], e["wilson95"])
            self.assertEqual(c["usage"]["coverage"], e["coverage"])
            self.assertEqual(c["usage"]["known_subtotal"], e["known_subtotal"])
            self.assertFalse(c["usage"]["known_subtotal_is_full_usage"])
            self.assertEqual(c["cost"], {"status": "no pricing snapshot", "total": None, "per_pass": None})
            self.assertEqual(len(c["pass_duration_ms"]["values"]), e["grades"]["PASS"])

    def test_report_regenerates_identically_without_executing(self):
        before = {n: (self.out / n).read_bytes() for n in ("report.md", "report.csv", "summary.json")}
        with mock.patch.object(runner, "fake_execute", side_effect=AssertionError("executed")), \
                mock.patch.object(grader, "grade", side_effect=AssertionError("graded")):
            write_report(self.out)
        self.assertEqual(before, {n: (self.out / n).read_bytes() for n in before})

    def test_fake_is_labelled_everywhere(self):
        self.assertIn("FAKE EXECUTION", (self.out / "report.md").read_text())
        self.assertTrue(json.loads((self.out / "summary.json").read_text())["fake_execution"])
        rows = (self.out / "report.csv").read_text().splitlines()
        self.assertTrue(rows[0].startswith("fake_execution,"))
        self.assertTrue(all(r.startswith("true,") for r in rows[1:]))
        started = json.loads((self.out / "events.jsonl").read_text().splitlines()[0])
        self.assertEqual(started["executor"], {"kind": "fake", "track": "fake-offline"})

    def test_plan_is_balanced_and_seeded(self):
        plan = json.loads((self.out / "events.jsonl").read_text().splitlines()[0])["plan"]
        self.assertEqual(len(plan), 6)
        for block in (plan[0:2], plan[2:4], plan[4:6]):
            self.assertEqual(sorted(t.split("/")[0] for t in block), ["cfg-a", "cfg-b"])
        m = json.loads(MANIFEST.read_text())
        self.assertEqual(runner.plan_trials(m), runner.plan_trials(m))

    def test_existing_run_dir_is_never_overwritten(self):
        with self.assertRaises(FileExistsError):
            runner.run(MANIFEST, self.out)

    def test_interrupted_trial_stays_visible(self):
        events = self.out / "events.jsonl"
        lines = events.read_text().splitlines()
        cut = next(i for i, l in enumerate(lines) if json.loads(l)["type"] == "trial_started")
        events.write_text("\n".join(lines[:cut + 1]) + "\n")  # crash right after the first launch record
        s = summarize(*load_run(self.out))
        self.assertFalse(s["run_complete"])
        interrupted = [c for c in s["configs"] if c["interrupted"]]
        self.assertEqual(len(interrupted), 1)
        self.assertEqual(interrupted[0]["outcomes"]["unknown"], 1)
        self.assertEqual(interrupted[0]["operational_success"]["denominator"], 1)

    def test_tampered_record_is_rejected(self):
        (self.out / "manifest.json").write_text((self.out / "manifest.json").read_text().replace("offline-001", "x"))
        with self.assertRaisesRegex(ValueError, "digests do not match"):
            load_run(self.out)

    def test_executor_crash_is_recorded_as_error(self):
        out = Path(self.tmp.name) / "crash"
        runner.run(MANIFEST, out, execute=lambda *a: 1 / 0)
        s = summarize(*load_run(out))
        for c in s["configs"]:
            self.assertEqual(c["outcomes"]["error"], 3)
            self.assertEqual(c["operational_success"]["pass"], 0)
            self.assertIsNone(c["pass_duration_ms"]["median"])


class Grader(unittest.TestCase):
    def grade(self, data, claimed=None):
        with tempfile.TemporaryDirectory() as d:
            sealed = digest(data)
            (Path(d) / sealed.split(":")[1]).write_bytes(data)
            return grader.grade(TASK, d, claimed or sealed)[0]

    def test_known_good_and_known_bad(self):
        self.assertEqual(self.grade(canonical([-5, 1, 2, 3, 3])), "PASS")
        self.assertEqual(self.grade(canonical([3, 1, 2, 3, -5])), "FAIL")   # no-op
        self.assertEqual(self.grade(canonical([3, 3, 2, 1, -5])), "FAIL")   # wrong order
        self.assertEqual(self.grade(canonical([-5, 1, 2, 3])), "FAIL")      # dropped element (hardcoded/partial)
        self.assertEqual(self.grade(canonical([True, 1, 2, 3, 3])), "FAIL")
        self.assertEqual(self.grade(b"not json"), "FAIL")

    def test_candidate_modified_after_seal_is_invalid(self):
        self.assertEqual(self.grade(canonical([-5, 1, 2, 3, 3]), claimed="sha256:" + "0" * 64), "INVALID")


class Wilson(unittest.TestCase):
    def test_reference_values(self):
        self.assertEqual(wilson95(0, 5), [0.0, 0.4345])
        self.assertEqual(wilson95(5, 5), [0.5655, 1.0])
        self.assertIsNone(wilson95(0, 0))


if __name__ == "__main__":
    unittest.main()
