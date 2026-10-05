"""AB5-04: cost and statistics against hand-computed values (never recomputed with production code)."""
import json
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_benchmark import runner  # noqa: E402
from agent_benchmark.pricing import price_usage, validate_pricing  # noqa: E402
from agent_benchmark.report import write_report  # noqa: E402
from agent_benchmark.schema import ValidationError, canonical  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
MANIFEST = FIXTURES / "manifest-offline-001.json"
PRICING = FIXTURES / "pricing-2026-10-05.json"
ALPHA = json.loads(PRICING.read_text())["models"]["fake-model-alpha"]
BETA = json.loads(PRICING.read_text())["models"]["fake-model-beta"]


def usage(i, o, c, completeness="complete"):
    return {"source": "t", "completeness": completeness, "input_tokens": i, "output_tokens": o, "cache_read_tokens": c}


def retry_executor(request, task, entry):
    """Two attempts (first errors, retry completes), each with its own usage summary 1000/200/400."""
    good = request["config_id"] == "cfg-a"
    data = sorted(task["input"]) if good else sorted(task["input"], reverse=True)
    ids = [request["request_id"] + s for s in ("-a1", "-a2")]
    return {"execution_id": "x-" + request["request_id"],
            "attempts": [{"attempt_id": ids[0], "outcome": "error"}, {"attempt_id": ids[1], "outcome": "completed"}],
            "outcome": "completed", "harness_completion": "success", "candidate": canonical(data),
            "usage_events": [{"attempt_id": a, "usage_event_id": a + "-sum", "kind": "summary",
                              "usage": usage(1000, 200, 400)} for a in ids]}


class PriceUsage(unittest.TestCase):
    def test_cache_not_included_in_input(self):
        # 1000*3 + 200*15 + 400*0.3 = 6120 per million
        self.assertEqual(price_usage(usage(1000, 200, 400), ALPHA), (Decimal("0.00612"), True))

    def test_cache_included_in_input_is_not_double_counted(self):
        # (1000-400)*0.002 + 200*0.01 + 400*0.0005 = 3.4 per thousand
        self.assertEqual(price_usage(usage(1000, 200, 400), BETA), (Decimal("0.0034"), True))

    def test_unit_change_gives_same_amount(self):
        per_token = {**ALPHA, "unit": "per_token", "input": "0.000003", "output": "0.000015", "cache_read": "0.0000003"}
        self.assertEqual(price_usage(usage(1000, 200, 400), per_token), (Decimal("0.00612"), True))

    def test_missing_rate_or_usage_is_not_zero(self):
        self.assertEqual(price_usage(None, ALPHA), (None, False))
        # cache rate unknown: known part 1000*3 + 200*15 = 6000 per million, not fully priced
        self.assertEqual(price_usage(usage(1000, 200, 400), {**ALPHA, "cache_read": None}), (Decimal("0.006"), False))
        self.assertEqual(price_usage(usage(50, None, None, "partial"), ALPHA), (Decimal("0.00015"), False))

    def test_contradictory_cache_overlap(self):
        self.assertEqual(price_usage(usage(100, 10, 400), BETA), (None, False))

    def test_snapshot_validation(self):
        p = json.loads(PRICING.read_text())
        for mutate, match in ((lambda m: m.update(currency="usd"), "ISO 4217"),
                              (lambda m: m.update(input=-1), "non-negative"),
                              (lambda m: m.update(unit="per_call"), "unit"),
                              (lambda m: m.pop("cache_read"), "explicit null")):
            bad = json.loads(json.dumps(p))
            mutate(bad["models"]["fake-model-alpha"])
            with self.assertRaisesRegex(ValidationError, match):
                validate_pricing(bad)
        with self.assertRaisesRegex(ValidationError, "basis"):
            validate_pricing({**p, "basis": "vibes"})


class ReportCost(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cost(self, s):
        return {c["config_id"]: c["cost"] for c in s["configs"]}

    def test_fixture_run_partial_usage(self):
        out = runner.run(MANIFEST, self.root / "r")
        cost = self.cost(write_report(out, PRICING))
        # cfg-a: r1 100*3+20*15 = 600 per million; r2 unknown; r3 partial 50*3 = 150 per million
        self.assertEqual(cost["cfg-a"]["coverage"], {"full": 1, "partial": 1, "unknown": 1})
        self.assertEqual((cost["cfg-a"]["known_subtotal"], cost["cfg-a"]["currency"]), ("0.00075", "USD"))
        self.assertIsNone(cost["cfg-a"]["total"])
        self.assertIsNone(cost["cfg-a"]["per_pass"])
        # cfg-b: r1 200*0.002 + 40*0.01 = 0.8 per thousand; timeout and error unknown
        self.assertEqual(cost["cfg-b"]["coverage"], {"full": 1, "partial": 0, "unknown": 2})
        self.assertEqual((cost["cfg-b"]["known_subtotal"], cost["cfg-b"]["currency"]), ("0.0008", "EUR"))
        self.assertIn("unknown", (out / "report.md").read_text())

    def test_retries_cache_and_zero_pass(self):
        out = runner.run(MANIFEST, self.root / "r", execute=retry_executor)
        s = write_report(out, PRICING)
        cost = self.cost(s)
        # cfg-a: 2 attempts x 0.00612 = 0.01224 per trial; 3 trials 0.03672; 3 PASS -> 0.01224 per PASS
        self.assertEqual((cost["cfg-a"]["total"], cost["cfg-a"]["per_pass"]), ("0.03672", "0.01224"))
        # cfg-b: 2 x 0.0034 = 0.0068 per trial; 3 trials 0.0204; 0 PASS -> no cost per successful solution
        self.assertEqual((cost["cfg-b"]["total"], cost["cfg-b"]["per_pass"]), ("0.0204", None))
        self.assertEqual(cost["cfg-b"]["per_pass_note"], "no successful solution (0 PASS)")
        cfg = {c["config_id"]: c for c in s["configs"]}
        self.assertEqual((cfg["cfg-a"]["first_attempt_pass"], cfg["cfg-a"]["after_retry_pass"]), (0, 3))
        self.assertFalse(s["cost_comparable"])  # USD vs EUR, no conversion

    def test_same_currency_is_comparable(self):
        p = json.loads(PRICING.read_text())
        p["models"]["fake-model-beta"]["currency"] = "USD"
        (self.root / "p.json").write_text(json.dumps(p))
        out = runner.run(MANIFEST, self.root / "r", execute=retry_executor)
        self.assertTrue(write_report(out, self.root / "p.json")["cost_comparable"])

    def test_missing_model_rate(self):
        p = json.loads(PRICING.read_text())
        del p["models"]["fake-model-beta"]
        (self.root / "p.json").write_text(json.dumps(p))
        out = runner.run(MANIFEST, self.root / "r", execute=retry_executor)
        cost = self.cost(write_report(out, self.root / "p.json"))
        self.assertEqual(cost["cfg-b"]["status"], "no rate for model 'fake-model-beta'")
        self.assertEqual((cost["cfg-b"]["total"], cost["cfg-b"]["coverage"]["unknown"]), (None, 3))

    def test_pricing_is_bound_to_the_run(self):
        out = runner.run(MANIFEST, self.root / "r")
        first = write_report(out, PRICING)
        self.assertEqual(write_report(out), first)  # later regeneration reuses the bound snapshot
        p = json.loads(PRICING.read_text())
        p["source"] = "another snapshot"
        (self.root / "p.json").write_text(json.dumps(p))
        with self.assertRaisesRegex(ValidationError, "different pricing snapshot"):
            write_report(out, self.root / "p.json")
        self.assertIn("pricing", first["input_digests"])

    def test_exclusions_have_their_own_denominator(self):
        shutil.copytree(FIXTURES, self.root / "fx")
        m = json.loads(MANIFEST.read_text())
        m["exclusions"] = [{"outcome": "error", "reason": "executor infrastructure"},
                           {"outcome": "timeout", "reason": "runner host limit"}]
        (self.root / "fx" / "m.json").write_text(json.dumps(m))
        s = write_report(runner.run(self.root / "fx" / "m.json", self.root / "r"))
        b = next(c for c in s["configs"] if c["config_id"] == "cfg-b")
        self.assertEqual((b["operational_success"]["pass"], b["operational_success"]["denominator"]), (1, 3))
        x = b["success_after_exclusions"]
        self.assertEqual((x["pass"], x["denominator"], x["excluded"]), (1, 1, 2))


if __name__ == "__main__":
    unittest.main()
