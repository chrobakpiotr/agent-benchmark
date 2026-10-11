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
from agent_benchmark.compare import compare, fisher_exact, pool  # noqa: E402
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

    def test_separated_wilson_intervals_claim_a_direction(self):
        def ten(candidate):
            def mutate(m):
                m["repetitions"] = 10
                m["executor"]["script"] = [{"config_id": c["config_id"], "repetition": r, "outcome": "completed",
                                            "candidate": candidate, "completion": None, "usage": None}
                                           for c in m["configs"] for r in range(1, 11)]
            return mutate
        p = self.pairs(self.run_offline("a", ten("good")), self.run_offline("b", ten("noop")))
        # hand-computed Wilson 95%: 10/10 -> [0.7225, 1.0], 0/10 -> [0.0, 0.2775]; they do not overlap
        self.assertEqual((p["cfg-a"]["pass"], p["cfg-a"]["correctness"]), (["10/10", "0/10"], "B lower"))
        p = self.pairs(self.run_offline("c", ten("noop")), self.run_offline("d", ten("good")))
        self.assertEqual(p["cfg-b"]["correctness"], "B higher")

    def test_fisher_exact_hand_computed(self):
        # Fisher's tea tasting: 4/4 vs 0/4 -> two-sided p = 2/70; 3/3 vs 0/3 -> 2/20; identical -> 1
        self.assertEqual(fisher_exact(4, 4, 0, 4), round(2 / 70, 4))
        self.assertEqual(fisher_exact(3, 3, 0, 3), 0.1)
        self.assertEqual(fisher_exact(2, 4, 2, 4), 1.0)
        self.assertIsNone(fisher_exact(0, 0, 1, 1))

    def test_pool_adds_identical_runs_and_excludes_others(self):
        a, b = self.run_offline("a"), self.run_offline("b")
        changed = self.run_offline("c", lambda m: m["configs"][0].update(model_requested="other-model"))
        p = pool([a, b, changed])
        self.assertEqual((len(p["included"]), [e["reasons"] for e in p["excluded"]]),
                         (2, [["config cfg-a: model_requested differs"]]))
        # offline-001 oracle: cfg-a 2/3 and cfg-b 1/3 per run, so 4/6 and 2/6 pooled
        self.assertEqual({c: (t["pass"], t["started"], t["runs"]) for c, t in p["configs"].items()},
                         {"cfg-a": (4, 6, 2), "cfg-b": (2, 6, 2)})
        self.assertEqual(p["pairs"][0]["fisher_p"], fisher_exact(4, 6, 2, 6))

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
