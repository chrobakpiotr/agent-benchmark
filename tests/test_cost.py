"""AB5-04: cost and statistics against hand-computed values (never recomputed with production code)."""
import json
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_benchmark import harness_port, runner  # noqa: E402
from agent_benchmark.pricing import price_scope, price_trial, validate_pricing  # noqa: E402
from agent_benchmark.report import write_report  # noqa: E402
from agent_benchmark.schema import ValidationError, canonical  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
MANIFEST = FIXTURES / "manifest-offline-001.json"
PRICING = FIXTURES / "pricing-2026-10-05.json"
ALPHA = json.loads(PRICING.read_text())["models"]["fake-model-alpha"]
BETA = json.loads(PRICING.read_text())["models"]["fake-model-beta"]


def units(i, o, cr, cw):
    return {"input_tokens": i, "output_tokens": o, "cache_read_tokens": cr, "cache_write_tokens": cw}


def retry_backend(request, task, entry, bundle_dir, evidence_root):
    """Contract result with two attempts (first errors, retry completes), each with a summary 1000/200/400/0.

    cfg-a reports cache separately, cfg-b reports cache included in input.
    """
    cfg_a = request["trial_id"].startswith("cfg-a/")
    data = sorted(task["input"]) if cfg_a else sorted(task["input"], reverse=True)
    result = harness_port.fake_backend(request, {**entry, "outcome": "completed", "completion": "accepted",
                                                 "usage": None}, canonical(data), evidence_root)
    first = {**result["attempts"][0], "attempt_id": "att-1", "outcome": "error"}
    second = {**result["attempts"][0], "attempt_id": "att-2", "outcome": "completed"}
    result["attempts"] = [first, second]
    result["usage_events"] = [{"contract_version": 1, "event_id": f"u-{a}", "attempt_id": a, "source": "provider",
                               "kind": "summary", "units": units(1000, 200, 400, 0),
                               "cache_semantics": "separate" if cfg_a else "included_in_input"}
                              for a in ("att-1", "att-2")]
    result["usage_completeness"] = "complete"
    return result


def manifest_copy(root, **changes):
    shutil.copytree(FIXTURES, root / "fx")
    m = json.loads(MANIFEST.read_text())
    m.update(changes)
    (root / "fx" / "m.json").write_text(json.dumps(m))
    return root / "fx" / "m.json"


class PriceScope(unittest.TestCase):
    def test_cache_separate(self):
        # 1000*3 + 200*15 + 400*0.3 + 0*3.75 = 6120 per million
        self.assertEqual(price_scope(units(1000, 200, 400, 0), "separate", ALPHA), (Decimal("0.00612"), True))

    def test_cache_included_in_input_is_not_double_counted(self):
        # (1000-400)*0.002 + 200*0.01 + 400*0.0005 = 3.4 per thousand
        self.assertEqual(price_scope(units(1000, 200, 400, 0), "included_in_input", BETA), (Decimal("0.0034"), True))

    def test_unit_change_gives_same_amount(self):
        per_token = {**ALPHA, "unit": "per_token", "input": "0.000003", "output": "0.000015",
                     "cache_read": "0.0000003", "cache_write": "0.00000375"}
        self.assertEqual(price_scope(units(1000, 200, 400, 0), "separate", per_token), (Decimal("0.00612"), True))

    def test_missing_rate_or_usage_is_not_zero(self):
        # cache_read rate unknown: known part 1000*3 + 200*15 = 6000 per million, not fully priced
        self.assertEqual(price_scope(units(1000, 200, 400, 0), "separate", {**ALPHA, "cache_read": None}),
                         (Decimal("0.006"), False))
        # partial units: 50*3 = 150 per million
        self.assertEqual(price_scope(units(50, None, None, None), "separate", ALPHA), (Decimal("0.00015"), False))
        # cache_write tokens without a rate: (1000*0.002 + 200*0.01) per thousand, not fully priced
        self.assertEqual(price_scope(units(1000, 200, 0, 100), "separate", BETA), (Decimal("0.004"), False))
        self.assertEqual(price_trial({"usage_scopes": [], "measurement_quality": "unknown"}, ALPHA), (None, False))

    def test_unknown_cache_semantics(self):
        # input and cache cannot be split: only output 200*15 = 3000 per million
        self.assertEqual(price_scope(units(1000, 200, 400, 0), "unknown", ALPHA), (Decimal("0.003"), False))
        # no cache tokens at all: nothing to split, 1000*3 + 200*15 = 6000 per million
        self.assertEqual(price_scope(units(1000, 200, 0, 0), "unknown", ALPHA), (Decimal("0.006"), True))

    def test_contradictory_cache_overlap(self):
        self.assertEqual(price_scope(units(100, 10, 400, 0), "included_in_input", BETA), (None, False))

    def test_snapshot_validation(self):
        p = json.loads(PRICING.read_text())
        for mutate, match in ((lambda m: m.update(currency="usd"), "ISO 4217"),
                              (lambda m: m.update(input=-1), "non-negative"),
                              (lambda m: m.update(unit="per_call"), "unit"),
                              (lambda m: m.pop("cache_write"), "explicit null"),
                              (lambda m: m.update(input_includes_cache_read=True), "unknown fields")):
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
        out = runner.run(manifest_copy(self.root, retry_policy={"max_attempts": 2}), self.root / "r",
                         execute=retry_backend)
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
        out = runner.run(manifest_copy(self.root, retry_policy={"max_attempts": 2}), self.root / "r",
                         execute=retry_backend)
        self.assertTrue(write_report(out, self.root / "p.json")["cost_comparable"])

    def test_missing_model_rate(self):
        p = json.loads(PRICING.read_text())
        del p["models"]["fake-model-beta"]
        (self.root / "p.json").write_text(json.dumps(p))
        out = runner.run(manifest_copy(self.root, retry_policy={"max_attempts": 2}), self.root / "r",
                         execute=retry_backend)
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
        m = manifest_copy(self.root, exclusions=[{"outcome": "error", "reason": "executor infrastructure"},
                                                 {"outcome": "timeout", "reason": "runner host limit"}])
        s = write_report(runner.run(m, self.root / "r"))
        b = next(c for c in s["configs"] if c["config_id"] == "cfg-b")
        self.assertEqual((b["operational_success"]["pass"], b["operational_success"]["denominator"]), (1, 3))
        x = b["success_after_exclusions"]
        self.assertEqual((x["pass"], x["denominator"], x["excluded"]), (1, 1, 2))


if __name__ == "__main__":
    unittest.main()
