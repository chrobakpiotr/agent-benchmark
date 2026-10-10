"""AB5-07: the runner drives a real agent CLI through harness AgentCliBackend (fake `codex`/`claude` on PATH here).

No provider is called. Run directories go under `runs/` because the harness refuses evidence roots in /tmp or
$TMPDIR (agent-writable).
"""
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_benchmark import harness_port, runner  # noqa: E402
from agent_benchmark.report import load_run, reduce_events, write_report  # noqa: E402
from agent_benchmark.schema import ValidationError  # noqa: E402

MANIFEST = ROOT / "tests" / "fixtures" / "manifest-agent-cli.json"
FAKE_CODEX = r"""#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
if args[:2] == ["login", "status"]:
    print("Logged in using ChatGPT"); sys.exit(0)
if args and args[0] == "sandbox":
    sys.exit(0)
if args and args[0] == "exec":
    prompt = sys.stdin.read()
    assert "validate_result" in prompt and "expected" not in prompt.lower(), prompt
    with open("src/agent_harness/contract.py", "a") as f:
        f.write("# edited by the fake agent\n")
    print(json.dumps({"type": "thread.started", "thread_id": "t1"}))
    print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 40,
                                                          "cache_write_input_tokens": 0, "output_tokens": 7}}))
    sys.exit(0)
sys.exit(2)
"""
FAKE_CLAUDE = r"""#!/usr/bin/env python3
import json, sys
if sys.argv[1:3] == ["auth", "status"]:
    print(json.dumps({"loggedIn": True, "authMethod": "claude.ai"})); sys.exit(0)
sys.exit(2)
"""
BILLING = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK",
           "CLAUDE_CODE_USE_VERTEX", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN", "OPENAI_API_KEY")


class AgentCliRun(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / "runs" / f"test-{uuid.uuid4().hex[:8]}"
        (self.root / "bin").mkdir(parents=True)
        for name, body in (("codex", FAKE_CODEX), ("claude", FAKE_CLAUDE)):
            path = self.root / "bin" / name
            path.write_text(body)
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        env = {k: v for k, v in os.environ.items() if k not in BILLING}
        env["PATH"] = f"{self.root / 'bin'}{os.pathsep}{os.environ['PATH']}"
        self.env = mock.patch.dict(os.environ, env, clear=True)
        self.env.start()
        runner._SESSIONS.clear()
        # no Docker in unit tests: by default the grading target is unavailable
        self.session = mock.patch.object(harness_port, "GradingSession",
                                         side_effect=ValidationError("grading target did not qualify"))
        self.session.start()

    def tearDown(self):
        self.session.stop()
        self.env.stop()
        shutil.rmtree(self.root)

    def test_real_cli_trial_is_recorded_sealed_and_left_ungraded(self):
        out = runner.run(MANIFEST, self.root / "run")
        s = write_report(out)
        row = reduce_events(load_run(out)[2])["trials"][0]
        self.assertEqual((row["outcome"], row["isolation_level"], row["grade"]), ("completed", "controlled", None))
        self.assertEqual(row["usage"], {"input_tokens": 100, "output_tokens": 7, "cache_read_tokens": 40,
                                        "cache_write_tokens": 0})
        patch = (out / "candidates" / row["candidate_digest"].split(":")[1]).read_text()
        self.assertIn("+# edited by the fake agent", patch)
        self.assertNotIn(".git/", patch)
        self.assertFalse(s["fake_execution"])
        self.assertEqual(s["configs"][0]["cost"]["status"], "subscription, not priced")
        self.assertIn("graded only on the qualified Docker target", s["banner"])
        evidence = out / "evidence" / row["request_id"]
        self.assertEqual(json.loads((evidence / "backend-notes.json").read_text()),
                         {"rejection_reason": None, "withheld": None})
        self.assertTrue((out / "workspaces" / row["request_id"] / ".git").is_dir())  # beside, not around, evidence

    def test_candidate_is_graded_only_through_the_qualified_session(self):
        calls = []

        class FakeSession:  # stands in for harness QualifiedDockerBackend; never runs the candidate on this host
            isolation = {"track": "qualified", "qualification_digest": "sha256:" + "a" * 64}
            fired = [None]

            def __init__(self, out, cases_path, driver, job_id):
                calls.append((cases_path.name, job_id))

            def run_cases(self, ws, cases, run_dir, env, limit):
                self.workspace_patched = "# edited by the fake agent" in (ws / "src/agent_harness/contract.py").read_text()
                return True, 0, b"{}"  # no answers: every hidden case fails
        self.session.stop()
        with mock.patch.object(harness_port, "GradingSession", FakeSession):
            out = runner.run(MANIFEST, self.root / "run")
        self.session.start()
        grades = [json.loads(l) for l in (out / "events.jsonl").read_text().splitlines()
                  if json.loads(l)["type"] == "grade"]
        self.assertEqual([(g["result"], g["isolation"]["track"]) for g in grades], [("FAIL", "qualified")])
        self.assertEqual(grades[0]["isolation"]["limit_fired"], None)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "cases.json")

    def test_run_directory_in_temp_is_refused_before_anything_starts(self):
        out = Path(tempfile.mkdtemp()) / "run"
        try:
            with self.assertRaisesRegex(ValidationError, "agent CLIs can write"):
                runner.run(MANIFEST, out)
            self.assertFalse(out.exists())
        finally:
            shutil.rmtree(out.parent)

    def test_billing_variable_stops_the_run(self):
        with mock.patch.dict(os.environ, {"CODEX_API_KEY": "sk-x"}):
            with self.assertRaisesRegex(ValidationError, "zero-spend preflight failed: CODEX_API_KEY"):
                runner.run(MANIFEST, self.root / "run")
        self.assertFalse((self.root / "run").exists())


if __name__ == "__main__":
    unittest.main()
