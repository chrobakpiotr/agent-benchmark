"""AB5-08: comparison of two recorded runs (comparability first, correctness before cost). Hand-computed oracles."""
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_benchmark import cli, runner  # noqa: E402
from agent_benchmark.compare import compare  # noqa: E402
from agent_benchmark.report import write_report  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
PRICING = FIXTURES / "pricing-2026-10-05.json"


class Compare(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copytree(FIXTURES, self.root / "fx")

    def tearDown(self):
        self.tmp.cleanup()

    def run_offline(self, name, mutate=None):
        m = json.loads((FIXTURES / "manifest-offline-001.json").read_text())
        if mutate:
            mutate(m)
        path = self.root / "fx" / f"{name}.json"
        path.write_text(json.dumps(m))
        out = runner.run(path, self.root / name)
        write_report(out)
        return out

    def pairs(self, a, b):
        return {p["config_id"]: p for p in compare(a, b)["configs"]}

    def test_identical_configs_are_comparable_and_overlapping_wilson_claims_nothing(self):
        p = self.pairs(self.run_offline("a"), self.run_offline("b"))
        self.assertEqual((p["cfg-a"]["comparable"], p["cfg-a"]["pass"]), (True, ["2/3", "2/3"]))
        self.assertEqual((p["cfg-b"]["comparable"], p["cfg-b"]["pass"]), (True, ["1/3", "1/3"]))
        self.assertEqual(p["cfg-a"]["correctness"], "no evidence of a difference")
        self.assertEqual(p["cfg-a"]["cost"], "not compared: not fully priced on both sides")

    def test_changed_prompt_or_model_makes_only_that_config_not_comparable(self):
        a = self.run_offline("a")
        prompt = self.pairs(a, self.run_offline("b", lambda m: m["configs"][0].update(prompt_digest="sha256:" + "1" * 64)))
        self.assertEqual((prompt["cfg-a"]["comparable"], prompt["cfg-a"]["reasons"]), (False, ["prompt_digest changed"]))
        self.assertTrue(prompt["cfg-b"]["comparable"])
        self.assertTrue(prompt["cfg-a"]["correctness"].startswith("not compared:"))
        model = self.pairs(a, self.run_offline("c", lambda m: m["configs"][0].update(model_requested="fake-model-gamma")))
        self.assertEqual(model["cfg-a"]["reasons"], ["model_requested changed"])

    def test_pricing_on_one_side_only_is_not_a_cost_comparison(self):
        a, b = self.run_offline("a"), self.run_offline("b")
        write_report(a, PRICING)
        self.assertEqual(self.pairs(a, b)["cfg-a"]["cost"], "not compared: not fully priced on both sides")

    def test_changed_task_or_grader_is_never_comparable(self):
        real = runner.run(FIXTURES / "manifest-real-001.json", self.root / "real")
        ref = runner.run(FIXTURES / "manifest-reference-002.json", self.root / "ref")
        task = compare(real, ref)
        self.assertEqual(task["run_level_differences"], ["task changed"])  # same patch-io grader file
        self.assertFalse(any(p["comparable"] for p in task["configs"]))
        grader = compare(self.run_offline("a"), ref)
        self.assertEqual(grader["run_level_differences"], ["task changed", "grader changed"])

    def test_cli_prints_markdown_and_rejects_unreadable_runs(self):
        a, b = self.run_offline("a"), self.run_offline("b")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["compare", str(a), str(b), "--out", str(self.root / "cmp.md")]), 0)
        self.assertIn("| `cfg-a` | yes | 2/3 / 2/3 |", (self.root / "cmp.md").read_text())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["compare", str(a), str(self.root / "missing")]), 2)


if __name__ == "__main__":
    unittest.main()
