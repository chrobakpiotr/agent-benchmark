"""AB5-06a: the benchmark consumes the pinned agent-harness execution contract v1 through one adapter."""
import json
import re
import shutil
import sys
import tempfile
import unittest
from importlib import metadata, resources
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import agent_harness  # noqa: E402
from agent_harness import contract  # noqa: E402

from agent_benchmark import harness_port, runner  # noqa: E402
from agent_benchmark.report import reduce_events, summarize, load_run  # noqa: E402
from agent_benchmark.schema import EVENT_VERSION, ValidationError, digest, validate_event  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
PINNED_SHA = re.search(r"agent-harness\.git@([0-9a-f]{40})", (ROOT / "pyproject.toml").read_text()).group(1)


def golden(name):
    doc = json.loads((resources.files("agent_harness") / "contract_fixtures" / f"{name}.json").read_text())
    return doc["request"], doc["result"]


def ledger(request, terminal, usage):
    """Ledger records exactly as the runner writes them for one trial."""
    base = {"schema_version": EVENT_VERSION, "trial_id": request["trial_id"]}
    events = [{**base, "type": "trial_started", "event_id": "e0", "config_id": "cfg", "repetition": 1,
               "request_id": request["request_id"], "request_digest": contract.request_digest(request),
               "replaces": None, "started_utc": "t"},
              {**base, "type": "trial_finished", "event_id": "e1", "request_id": request["request_id"],
               "source": "executor", **terminal, "finished_utc": "t", "duration_ms": 1}]
    events += [{**base, "type": "usage", "event_id": f"u{i}", **u} for i, u in enumerate(usage)]
    for i, e in enumerate(events):
        validate_event(e, f"e{i}")
    return reduce_events(events)["trials"][0]


class Pin(unittest.TestCase):
    def test_installed_contract_matches_pin(self):
        self.assertEqual((agent_harness.__version__, contract.CONTRACT_VERSION), ("0.1.0", 1))
        direct = json.loads(metadata.distribution("agent-harness").read_text("direct_url.json") or "{}")
        if "vcs_info" in direct:  # installed from git: must be exactly the pinned commit
            self.assertEqual(direct["vcs_info"]["commit_id"], PINNED_SHA)

    def test_only_public_contract_api_is_used(self):
        for path in (ROOT / "src" / "agent_benchmark").glob("*.py"):
            text = path.read_text()
            for line in re.findall(r"^\s*(?:from|import) agent_harness.*$", text, re.M):
                self.assertIn(line.strip(), {"from agent_harness import contract",
                                             "from agent_harness.contract import ERROR_CODES, OUTCOMES"}, path.name)
            self.assertNotRegex(text, r"contract\._", path.name)


class GoldenFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "cand").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, name, result=None):
        request, golden_result = golden(name)
        terminal, usage = harness_port.import_result(request, result or golden_result, self.root, self.root / "cand")
        return request, terminal, ledger(request, terminal, usage)

    def test_success(self):
        _, terminal, row = self.load("success")
        self.assertEqual((row["outcome"], row["completion"], row["drain"]), ("completed", "accepted", "confirmed"))
        # summary 1200/300/0/0 is authoritative; the stream event 100/20 is not added
        self.assertEqual(row["usage"], {"input_tokens": 1200, "output_tokens": 300, "cache_read_tokens": 0,
                                        "cache_write_tokens": 0})
        self.assertEqual(row["measurement_quality"], "complete")
        self.assertEqual(terminal["candidate_digest"], "sha256:" + "c" * 64)
        self.assertEqual(list((self.root / "cand").iterdir()), [])  # no bytes behind the reference: not sealed

    def test_fail_is_completion_rejected_not_error(self):
        _, _, row = self.load("fail")
        self.assertEqual((row["outcome"], row["completion"], len(row["attempt_ids"])), ("completed", "rejected", 2))
        # two attempts: 800+900 input, output known only for the first
        self.assertEqual((row["usage"]["input_tokens"], row["usage"]["output_tokens"]), (1700, 100))
        self.assertEqual(row["measurement_quality"], "partial")

    def test_timeout_unknown_and_rejected(self):
        for name, outcome, drain, error_code in (("timeout", "timeout", "unconfirmed", None),
                                                 ("unknown-terminal", "unknown", "unconfirmed", None),
                                                 ("missing-qualification", "rejected", None, "NOT_QUALIFIED")):
            _, terminal, row = self.load(name)
            self.assertEqual((row["outcome"], row["drain"], row["error_code"]), (outcome, drain, error_code), name)
            self.assertEqual((row["usage"], row["measurement_quality"]), (None, "unknown"), name)
            self.assertIsNone(terminal["error"], name)

    def test_contract_violation_never_becomes_success(self):
        _, result = golden("success")
        for bad, code in (({**result, "request_id": "req-other"}, "BINDING_MISMATCH"),
                          ({**result, "contract_version": 2}, "VERSION_MISMATCH"),
                          ({**result, "completion": "accepted", "outcome": "timeout"}, "MALFORMED")):
            _, terminal, row = self.load("success", bad)
            self.assertEqual((row["outcome"], row["completion"], row["candidate_digest"]), ("unknown", None, None))
            self.assertTrue(terminal["error"].startswith(f"contract {code}:"), terminal["error"])

    def test_candidate_reference_is_verified_before_sealing(self):
        request, result = golden("success")
        data = b"candidate bytes"
        (self.root / "candidate").mkdir()
        (self.root / "candidate" / "ok").write_bytes(data)
        ref = {"path": "candidate/ok", "sha256": digest(data), "size": len(data)}
        self.load("success", {**result, "candidate": ref})
        self.assertEqual([p.name for p in (self.root / "cand").iterdir()], [digest(data).split(":")[1]])
        shutil.rmtree(self.root / "cand")
        (self.root / "cand").mkdir()
        outside = self.root.parent / f"outside-{self.root.name}"
        outside.write_bytes(data)
        try:
            (self.root / "candidate" / "link").symlink_to(outside)
            for bad in ({**ref, "size": len(data) + 1}, {**ref, "sha256": "sha256:" + "0" * 64},
                        {**ref, "path": "candidate/link"}, {**ref, "path": "candidate/missing"}):
                _, terminal, _ = self.load("success", {**result, "candidate": bad})
                self.assertEqual(terminal["candidate_digest"], bad["sha256"])  # claimed digest stays visible
            self.assertEqual(list((self.root / "cand").iterdir()), [])
        finally:
            outside.unlink()


class RunnerOverContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copytree(FIXTURES, self.root / "fx")

    def tearDown(self):
        self.tmp.cleanup()

    def manifest(self, mutate):
        m = json.loads((FIXTURES / "manifest-offline-001.json").read_text())
        mutate(m)
        (self.root / "fx" / "m.json").write_text(json.dumps(m))
        return self.root / "fx" / "m.json"

    def test_rejected_counts_in_denominator_and_is_excludable(self):
        def mutate(m):
            m["executor"]["script"][4].update(outcome="rejected")  # cfg-b r2
            m["exclusions"] = [{"outcome": "rejected", "reason": "backend unavailable"}]
        out = runner.run(self.manifest(mutate), self.root / "r")
        b = next(c for c in summarize(*load_run(out))["configs"] if c["config_id"] == "cfg-b")
        self.assertEqual((b["outcomes"]["rejected"], b["operational_success"]["denominator"]), (1, 3))
        self.assertEqual(b["success_after_exclusions"]["denominator"], 2)

    def test_raw_contract_documents_are_kept_as_evidence(self):
        out = runner.run(FIXTURES / "manifest-offline-001.json", self.root / "r")
        dirs = sorted((out / "evidence").iterdir())
        self.assertEqual(len(dirs), 6)
        request = json.loads((dirs[0] / "request.json").read_text())
        contract.validate_result(json.loads((dirs[0] / "result.json").read_text()), request)

    def test_config_that_cannot_be_a_contract_request_is_rejected_before_launch(self):
        out = self.root / "r"
        with self.assertRaisesRegex(ValidationError, "cannot be expressed"):
            runner.run(self.manifest(lambda m: m["configs"][0].update(model_requested="model with spaces")), out)
        self.assertFalse(any(json.loads(l)["type"] == "trial_started"
                             for l in (out / "events.jsonl").read_text().splitlines()))


if __name__ == "__main__":
    unittest.main()
