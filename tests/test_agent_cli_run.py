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

import agent_harness  # noqa: E402
from agent_benchmark import harness_port, runner  # noqa: E402
from agent_benchmark.report import load_run, reduce_events, write_report  # noqa: E402
from agent_benchmark.schema import ValidationError, digest, validate_manifest  # noqa: E402

MANIFEST = ROOT / "tests" / "fixtures" / "manifest-agent-cli.json"
FAKE_CODEX = r"""#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args[:2] == ["login", "status"]:
    print("Logged in using ChatGPT"); sys.exit(0)
if args == ["--version"]:
    print(os.environ.get("FAKE_CODEX_VERSION", "codex-cli 0.0-fake")); sys.exit(0)
if args and args[0] == "sandbox":  # runs the command like a sandbox that blocks writes outside the workspace
    if os.environ.get("FAKE_CODEX_NO_SANDBOX"):  # the CLI is installed but its sandbox fails
        sys.exit(1)
    import re, subprocess
    cmd = args[args.index("--") + 1:]
    if cmd[:2] == ["sh", "-c"]:
        cmd = ["sh", "-c", re.sub(r"echo x > \S+", "true", cmd[2])]  # the write the sandbox would block
    sys.exit(subprocess.run(cmd).returncode)
if args and args[0] == "exec":
    prompt = sys.stdin.read()
    if os.environ.get("FAKE_CODEX_LIMIT"):  # the subscription limit is exhausted mid-run
        print(json.dumps({"type": "turn.failed", "error": {"message": "usage limit reached"}}))
        sys.exit(1)
    assert "validate_result" in prompt and "expected" not in prompt.lower(), prompt
    target = "README.md" if "Another engineer" in prompt else "src/agent_harness/contract.py"  # reviewer vs builder
    with open(target, "a") as f:
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
        self.assertEqual(s["configs"][0]["usage"]["processed_input_tokens"], 100)  # cache inside input
        self.assertIn("graded only on the qualified Docker target", s["banner"])
        evidence = out / "evidence" / row["request_id"]
        self.assertEqual(json.loads((evidence / "backend-notes.json").read_text()),
                         {"rejection_reason": None, "withheld": None, "error": None, "requests": None})
        self.assertTrue((out / "workspaces" / row["request_id"] / ".git").is_dir())  # beside, not around, evidence
        self.assertIn(f"{row['trial_id']} left ungraded: grading target did not qualify",
                      (out / "warnings.log").read_text())  # the reason survives truncated console output
        self.assertIn("(host load [", (out / "warnings.log").read_text())

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
        self.assertEqual(len(grades[0]["isolation"]["host_load"]), 3)  # shared-host load at grading time
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "cases.json")

    def test_provider_error_stops_the_run_and_leaves_the_trial_ungraded(self):
        m = json.loads(MANIFEST.read_text())
        m.update(repetitions=2, task={**m["task"], "path": str((MANIFEST.parent / m["task"]["path"]).resolve())})
        path = self.root / "m.json"
        path.write_text(json.dumps(m))
        with mock.patch.dict(os.environ, {"FAKE_CODEX_LIMIT": "1"}):
            with self.assertRaisesRegex(ValidationError, r"provider error \((quota_exhausted|provider_error), resets "):
                runner.run(path, self.root / "run")
        events = [json.loads(l) for l in (self.root / "run" / "events.jsonl").read_text().splitlines()]
        finished = [e for e in events if e["type"] == "trial_finished"]
        self.assertEqual([(e["outcome"], e["error_code"]) for e in finished], [("error", "PROVIDER_ERROR")])
        self.assertFalse(any(e["type"] in ("grade", "run_finished") for e in events))  # second trial stays planned
        notes = json.loads(next((self.root / "run" / "evidence").glob("*/backend-notes.json")).read_text())
        self.assertIn(notes["error"]["kind"], ("quota_exhausted", "provider_error"))

    def reviewer_manifest(self, **reviewer):
        m = json.loads(MANIFEST.read_text())
        m["task"] = {**m["task"], "path": str((MANIFEST.parent / m["task"]["path"]).resolve())}
        m["configs"][0].update(workflow="builder-reviewer", reviewer={"cli": "codex", "model": "gpt-6.1-sol", **reviewer})
        path = self.root / "m.json"
        path.write_text(json.dumps(m))
        return path

    def test_builder_reviewer_trial_records_both_launches_and_the_cumulative_candidate(self):
        out = runner.run(self.reviewer_manifest(), self.root / "run")
        s = write_report(out)
        row = reduce_events(load_run(out)[2])["trials"][0]
        self.assertEqual(row["attempt_ids"], ["builder:attempt-1", "reviewer:attempt-1"])
        self.assertEqual(row["usage"], {"input_tokens": 200, "output_tokens": 14, "cache_read_tokens": 80,
                                        "cache_write_tokens": 0})  # both launches count towards the trial
        patch = (out / "candidates" / row["candidate_digest"].split(":")[1]).read_text()
        self.assertIn("contract.py", patch)  # builder edit
        self.assertIn("README.md", patch)  # reviewer edit, sealed cumulatively from the same base
        self.assertEqual(len(list((out / "evidence").iterdir())), 2)  # builder and reviewer evidence roots
        self.assertEqual(s["configs"][0]["after_retry_pass"], 0)

    def test_builder_error_skips_the_reviewer(self):
        with mock.patch.dict(os.environ, {"FAKE_CODEX_LIMIT": "1"}):
            with self.assertRaisesRegex(ValidationError, "provider error"):
                runner.run(self.reviewer_manifest(), self.root / "run")
        events = [json.loads(l) for l in (self.root / "run" / "events.jsonl").read_text().splitlines()]
        finished = [e for e in events if e["type"] == "trial_finished"]
        self.assertEqual([a["attempt_id"] for a in finished[0]["attempts"]], ["builder:attempt-1"])
        self.assertEqual(len(list((self.root / "run" / "evidence").iterdir())), 1)

    def test_reviewer_config_rules(self):
        m = json.loads(MANIFEST.read_text())
        for change, error in (({"workflow": "builder-reviewer"}, "required exactly when"),
                              ({"reviewer": {"cli": "codex", "model": "x"}}, "required exactly when"),
                              ({"workflow": "builder-reviewer", "reviewer": {"cli": "gemini", "model": "x"}}, "reviewer.cli")):
            bad = json.loads(json.dumps(m))
            bad["configs"][0].update(change)
            with self.assertRaisesRegex(ValidationError, error):
                validate_manifest(bad)
        fake = json.loads((MANIFEST.parent / "manifest-offline-001.json").read_text())
        fake["configs"][0].update(workflow="builder-reviewer", reviewer={"cli": "codex", "model": "x"})
        with self.assertRaisesRegex(ValidationError, "needs the agent-cli executor"):
            validate_manifest(fake)

    def test_cli_versions_are_recorded_and_resume_refuses_a_changed_cli(self):
        with mock.patch.dict(os.environ, {"FAKE_CODEX_LIMIT": "1"}):
            with self.assertRaises(ValidationError):
                runner.run(self.reviewer_manifest(), self.root / "run")  # stops after the builder error
        started = json.loads((self.root / "run" / "events.jsonl").read_text().splitlines()[0])
        self.assertEqual(started["executor"]["cli_versions"], {"codex": "codex-cli 0.0-fake"})
        with mock.patch.dict(os.environ, {"FAKE_CODEX_VERSION": "codex-cli 9.9-fake"}):
            with self.assertRaisesRegex(ValidationError, "CLI versions changed"):
                runner.resume(self.root / "run")

    def test_a_completed_trial_without_a_published_candidate_is_invalid_with_the_reason(self):
        real = harness_port.import_result

        def withheld(*args):  # the harness withheld the agent's output (AH5-12b): completed, no candidate
            terminal, usage = real(*args)
            return {**terminal, "candidate_digest": None}, usage
        note = {"reason_code": "OUTPUT_LIMIT_EXCEEDED", "artifacts": ["candidate", "agent-output"],
                "size": 9000000, "limit": 8388608, "size_is_lower_bound": True}
        with mock.patch.object(harness_port, "import_result", side_effect=withheld), \
                mock.patch.object(harness_port, "withheld_summary", return_value=note):
            out = runner.run(MANIFEST, self.root / "run")
        row = reduce_events(load_run(out)[2])["trials"][0]
        self.assertEqual((row["outcome"], row["grade"]), ("completed", "INVALID"))  # never PASS, never a grader FAIL
        grade = [json.loads(l) for l in (out / "events.jsonl").read_text().splitlines() if '"grade"' in l][0]
        self.assertEqual(grade["criteria"], [{"criterion": "candidate_published", "passed": False,
                                              "detail": {"withheld": note}}])
        s = write_report(out)["configs"][0]
        self.assertEqual((s["started"], s["operational_success"]["pass"]), (1, 0))  # stays in the denominator

    def test_withheld_note_is_found_by_artifact_name_and_keeps_no_content(self):
        ev = self.root / "ev"
        ev.mkdir()
        body = json.dumps({"schema_version": 1, "reason_code": "CREDENTIAL_SHAPED_OUTPUT", "artifacts": ["agent-stderr"],
                           "size": 12, "limit": None, "size_is_lower_bound": False, "secret_detected": False,
                           "note": "free text", "match": "sk-secret",
                           "details": [{"artifact": "agent-stderr", "reason_code": "CREDENTIAL_SHAPED_OUTPUT",
                                        "size": 12, "limit": None, "size_is_lower_bound": False, "excerpt": "x"}]}
                          ).encode()
        (ev / "withheld.json").write_bytes(body)
        ref = {"name": "withheld", "path": "withheld.json", "size": len(body), "sha256": digest(body)}
        other = {"name": "agent-stderr", "path": "x", "size": 1, "sha256": "sha256:" + "0" * 64}
        got = harness_port.withheld_summary({"artifacts": [other, ref]}, ev)
        self.assertEqual(got["reason_code"], "CREDENTIAL_SHAPED_OUTPUT")
        self.assertNotIn("match", got)
        self.assertNotIn("note", got)
        self.assertEqual(got["details"], [{"artifact": "agent-stderr", "reason_code": "CREDENTIAL_SHAPED_OUTPUT",
                                           "size": 12, "limit": None, "size_is_lower_bound": False}])
        self.assertIsNone(harness_port.withheld_summary({"artifacts": [other]}, ev))

    def test_a_sandbox_the_harness_rejects_stops_the_run(self):
        with mock.patch.dict(os.environ, {"FAKE_CODEX_NO_SANDBOX": "1"}):
            with self.assertRaisesRegex(ValidationError, "CAPABILITY_UNSUPPORTED.*run stopped"):
                runner.run(MANIFEST, self.root / "run")
        rows = reduce_events(load_run(self.root / "run")[2])["trials"]
        self.assertEqual([(r["outcome"], r["error_code"]) for r in rows], [("rejected", "CAPABILITY_UNSUPPORTED")])

    def test_harness_identity_is_recorded_reported_and_resume_refuses_a_changed_harness(self):
        with mock.patch.dict(os.environ, {"FAKE_CODEX_LIMIT": "1"}):
            with self.assertRaises(ValidationError):
                runner.run(self.reviewer_manifest(), self.root / "run")
        started = json.loads((self.root / "run" / "events.jsonl").read_text().splitlines()[0])
        self.assertEqual(started["executor"]["harness"], harness_port.harness_identity())
        self.assertEqual(started["executor"]["harness"]["version"], agent_harness.__version__)
        write_report(self.root / "run")
        self.assertIn(f"- agent-harness: {agent_harness.__version__}", (self.root / "run" / "report.md").read_text())
        real = harness_port.harness_identity()
        self.assertEqual(real["fingerprint"]["method"], harness_port.FINGERPRINT_METHOD)
        edited = {**real, "fingerprint": {**real["fingerprint"], "digest": "sha256:" + "e" * 64}}  # same version/commit
        with mock.patch.object(harness_port, "harness_identity", return_value=edited):
            with self.assertRaisesRegex(ValidationError, "agent-harness changed"):
                runner.resume(self.root / "run")
        unknown = {**real, "fingerprint": {**real["fingerprint"], "digest": None}}
        with mock.patch.object(harness_port, "harness_identity", return_value=unknown):
            with self.assertRaisesRegex(ValidationError, "cannot be identified"):
                runner.resume(self.root / "run")
        runner._check_harness_unchanged(started["executor"]["harness"])  # the unchanged installation may resume

    def test_resume_of_a_run_recorded_before_fingerprints(self):
        """Old runs keep their record; they resume only if version and git commit match, never on version alone."""
        real = harness_port.harness_identity()
        runner._check_harness_unchanged({"version": real["version"], "commit": real["commit"]})
        with self.assertRaisesRegex(ValidationError, "no commit and no fingerprint"):
            runner._check_harness_unchanged({"version": real["version"], "commit": None})
        with self.assertRaisesRegex(ValidationError, "changed"):
            runner._check_harness_unchanged({"version": real["version"], "commit": "0" * 40})

    def test_fingerprint_reads_file_content_not_record_hashes(self):
        from importlib.metadata import PathDistribution
        site = self.root / "site"
        info = site / "agent_harness-9.9.dist-info"
        (site / "agent_harness" / "__pycache__").mkdir(parents=True)
        info.mkdir()
        (site / "agent_harness" / "contract.py").write_text("RULE = 1\n")
        (site / "agent_harness" / "__pycache__" / "contract.cpython-313.pyc").write_bytes(b"cache")
        (info / "METADATA").write_text("Name: agent-harness\nVersion: 9.9\n")
        (info / "INSTALLER").write_text("pip\n")
        (info / "RECORD").write_text("agent_harness/contract.py,sha256=stale,9\n"
                                     "agent_harness/__pycache__/contract.cpython-313.pyc,,\n"
                                     "agent_harness-9.9.dist-info/METADATA,,\nagent_harness-9.9.dist-info/INSTALLER,,\n"
                                     "agent_harness-9.9.dist-info/RECORD,,\n../../../bin/agent-harness,,\n")
        dist = PathDistribution(info)
        before = harness_port.harness_fingerprint(dist)
        (site / "agent_harness" / "__pycache__" / "contract.cpython-313.pyc").write_bytes(b"other cache")
        (info / "INSTALLER").write_text("uv\n")
        self.assertEqual(harness_port.harness_fingerprint(dist), before)  # caches and install details do not count
        (site / "agent_harness" / "contract.py").write_text("RULE = 2\n")  # same RECORD, changed code
        self.assertNotEqual(harness_port.harness_fingerprint(dist), before)
        (site / "agent_harness" / "contract.py").unlink()
        self.assertIsNone(harness_port.harness_fingerprint(dist))  # cannot be identified

    def test_pinned_cli_version_must_match_the_installed_one(self):
        m = json.loads(MANIFEST.read_text())
        m["task"] = {**m["task"], "path": str((MANIFEST.parent / m["task"]["path"]).resolve())}
        m["configs"][0]["cli_version"] = "codex-cli 1.2.3"
        path = self.root / "pinned.json"
        path.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValidationError, "manifest pins 'codex-cli 1.2.3'"):
            runner.run(path, self.root / "run")
        with mock.patch.dict(os.environ, {"FAKE_CODEX_VERSION": "codex-cli 1.2.3"}):
            runner.run(path, self.root / "run2")  # matching version runs

    def test_prompt_addendum_reaches_the_agent_and_is_part_of_the_identity(self):
        from agent_benchmark import harness_port as hp
        task = {"description": "Fix it.", "visible_checks": ["run x"]}
        plain, extra = hp.agent_prompt(task), hp.agent_prompt(task, "Check related inputs too.")
        self.assertNotIn("related", plain)
        self.assertIn("run x\n\nCheck related inputs too.\n\nWork only", extra)
        from agent_benchmark.compare import CONFIG_IDENTITY
        self.assertIn("prompt_addendum", CONFIG_IDENTITY)
        m = json.loads(MANIFEST.read_text())
        m["configs"][0]["prompt_addendum"] = 7
        with self.assertRaisesRegex(ValidationError, "prompt_addendum"):
            validate_manifest(m)

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
