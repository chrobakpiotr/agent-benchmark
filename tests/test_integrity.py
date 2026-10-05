"""AB5-03: trial integrity, dedup, reconciliation, replacement and corrections on the append-only ledger."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_benchmark import runner  # noqa: E402
from agent_benchmark.report import load_run, summarize  # noqa: E402
from agent_benchmark.schema import EVENT_VERSION, ValidationError  # noqa: E402

MANIFEST = Path(__file__).parent / "fixtures" / "manifest-offline-001.json"


class Crash(BaseException):
    """Simulates the process dying (not an executor error the runner could record)."""


def counting(crash_on=None):
    calls = []

    def execute(request, task, entry, bundle_dir):
        calls.append(request["trial_id"])
        if crash_on is not None and len(calls) == crash_on:
            raise Crash()
        return runner.fake_execute(request, task, entry, bundle_dir)
    return execute, calls


def lines(run_dir):
    return [json.loads(x) for x in (run_dir / "events.jsonl").read_text().splitlines()]


def write_lines(run_dir, events):
    (run_dir / "events.jsonl").write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events))


def append(run_dir, event):
    with open(run_dir / "events.jsonl", "a") as f:
        f.write(json.dumps({"schema_version": EVENT_VERSION, **event}, sort_keys=True) + "\n")


def summary(run_dir):
    return summarize(*load_run(run_dir))


def by_config(s, key):
    return {c["config_id"]: c[key] for c in s["configs"]}


class Integrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.full = runner.run(MANIFEST, self.root / "full")

    def tearDown(self):
        self.tmp.cleanup()

    def test_crash_between_launch_and_record_is_not_rerun(self):
        out = self.root / "crash"
        execute, _ = counting(crash_on=3)
        with self.assertRaises(Crash):
            runner.run(MANIFEST, out, execute=execute)
        crashed = lines(out)[0]["plan"][2]
        execute, calls = counting()
        runner.resume(out, execute=execute)
        self.assertNotIn(crashed, calls)
        self.assertEqual(len(calls), 3)  # only the never-started trials
        s = summary(out)
        row = next(r for r in s["trials"] if r["trial_id"] == crashed)
        self.assertEqual((row["outcome"], row["terminal_source"], row["grade"]), ("unknown", "reconciliation", None))
        self.assertEqual(sum(by_config(s, "started").values()), 6)
        self.assertTrue(s["run_complete"])
        self.assertTrue(s["integrity"]["ok"])

    def test_replacement_gets_new_identity_and_link(self):
        out = self.root / "crash"
        with self.assertRaises(Crash):
            runner.run(MANIFEST, out, execute=counting(crash_on=3)[0])
        crashed = lines(out)[0]["plan"][2]
        execute, calls = counting()
        runner.resume(out, replace_unknown=True, execute=execute)
        self.assertEqual(len(calls), 4)
        rows = {r["trial_id"]: r for r in summary(out)["trials"]}
        repl = rows[crashed + "/x1"]
        self.assertEqual(repl["replaces"], crashed)
        self.assertNotEqual(repl["request_id"], rows[crashed]["request_id"])
        self.assertEqual(rows[crashed]["outcome"], "unknown")  # the original stays visible
        self.assertEqual(sum(by_config(summary(out), "started").values()), 7)
        self.assertEqual(sum(by_config(summary(out), "replacements").values()), 1)

    def test_crash_after_terminal_before_grade(self):
        events = lines(self.full)
        cut = next(i for i, e in enumerate(events) if e["type"] == "trial_finished" and e["candidate_digest"])
        write_lines(self.full, events[:cut + 1])
        execute, calls = counting()
        runner.resume(self.full, execute=execute)
        self.assertNotIn(events[cut]["trial_id"], calls)
        s = summary(self.full)
        expected = summary(runner.run(MANIFEST, self.root / "ref"))
        self.assertEqual(by_config(s, "grades"), by_config(expected, "grades"))
        self.assertEqual(by_config(s, "outcomes"), by_config(expected, "outcomes"))
        self.assertTrue(s["integrity"]["ok"])

    def test_crash_before_launch_record_runs_the_trial(self):
        events = lines(self.full)
        cut = [i for i, e in enumerate(events) if e["type"] == "trial_started"][3]
        write_lines(self.full, events[:cut])
        execute, calls = counting()
        runner.resume(self.full, execute=execute)
        self.assertEqual(calls[0], events[cut]["trial_id"])
        s = summary(self.full)
        self.assertEqual(sum(by_config(s, "started").values()), 6)
        self.assertEqual(sum(by_config(s, "reconciled_unknown").values()), 0)

    def test_nothing_to_resume(self):
        with self.assertRaisesRegex(ValidationError, "nothing to resume"):
            runner.resume(self.full)

    def test_redelivered_event_is_counted_once(self):
        before = summary(self.full)
        with open(self.full / "events.jsonl", "a") as f:
            f.write((self.full / "events.jsonl").read_text().splitlines()[3] + "\n")
        after = summary(self.full)
        self.assertTrue(after["integrity"]["ok"])
        self.assertEqual(by_config(after, "usage"), by_config(before, "usage"))
        self.assertEqual(by_config(after, "grades"), by_config(before, "grades"))

    def test_same_event_id_different_body_keeps_first(self):
        before = summary(self.full)
        grade = next(e for e in lines(self.full) if e["type"] == "grade" and e["result"] == "FAIL")
        append(self.full, {**grade, "result": "PASS"})
        after = summary(self.full)
        self.assertEqual(by_config(after, "grades"), by_config(before, "grades"))
        self.assertEqual([c["kind"] for c in after["integrity"]["conflicts"]], ["event_id_reused"])

    def test_conflicting_terminal_does_not_overwrite(self):
        term = next(e for e in lines(self.full) if e["type"] == "trial_finished" and e["outcome"] == "timeout")
        append(self.full, {**term, "event_id": "late-terminal", "outcome": "completed"})
        s = summary(self.full)
        row = next(r for r in s["trials"] if r["trial_id"] == term["trial_id"])
        self.assertEqual(row["outcome"], "timeout")
        self.assertEqual([c["kind"] for c in s["integrity"]["conflicts"]], ["conflicting_terminal"])

    def test_stream_and_summary_overlap_not_double_counted(self):
        term = next(e for e in lines(self.full) if e["type"] == "trial_finished" and e["outcome"] == "timeout")
        aid = term["attempts"][0]["attempt_id"]

        def usage(eid, uid, kind, i, o, completeness="complete"):
            append(self.full, {"type": "usage", "event_id": eid, "trial_id": term["trial_id"], "attempt_id": aid,
                               "usage_event_id": uid, "kind": kind,
                               "usage": {"source": "test", "completeness": completeness, "input_tokens": i,
                                         "output_tokens": o, "cache_read_tokens": 0}})
        usage("e1", "s1", "stream", 10, 2)
        usage("e2", "s2", "stream", 5, 1)
        usage("e3", "s1", "stream", 10, 2)       # re-delivered stream event under a new envelope
        usage("e4", "sum", "summary", 15, 3)     # final summary covers the stream
        row = next(r for r in summary(self.full)["trials"] if r["trial_id"] == term["trial_id"])
        self.assertEqual((row["usage"]["input_tokens"], row["usage"]["output_tokens"]), (15, 3))
        self.assertEqual(row["measurement_quality"], "complete")
        cfg = term["trial_id"].split("/")[0]
        # hand-computed: fixture cfg-b subtotal 200/40 + this trial 15/3
        self.assertEqual(by_config(summary(self.full), "usage")[cfg]["known_subtotal"]["input_tokens"], 215)
        usage("e5", "s2", "stream", 99, 9)       # same usage_event_id, different body
        self.assertEqual([c["kind"] for c in summary(self.full)["integrity"]["conflicts"]], ["usage_event_id_reused"])

    def test_stream_only_sums_deltas(self):
        term = next(e for e in lines(self.full) if e["type"] == "trial_finished" and e["outcome"] == "timeout")
        aid = term["attempts"][0]["attempt_id"]
        for eid, i in (("e1", 10), ("e2", 5)):
            append(self.full, {"type": "usage", "event_id": eid, "trial_id": term["trial_id"], "attempt_id": aid,
                               "usage_event_id": eid, "kind": "stream",
                               "usage": {"source": "t", "completeness": "partial", "input_tokens": i,
                                         "output_tokens": None, "cache_read_tokens": None}})
        row = next(r for r in summary(self.full)["trials"] if r["trial_id"] == term["trial_id"])
        self.assertEqual(row["usage"], {"input_tokens": 15, "output_tokens": None, "cache_read_tokens": None})
        self.assertEqual(row["measurement_quality"], "partial")

    def test_invalidate_lowers_result_and_keeps_history(self):
        passed = next(e for e in lines(self.full) if e["type"] == "grade" and e["result"] == "PASS")
        before = by_config(summary(self.full), "grades")
        with self.assertRaisesRegex(ValidationError, "reason"):
            runner.invalidate(self.full, passed["trial_id"], " ")
        with self.assertRaisesRegex(ValidationError, "unknown trial"):
            runner.invalidate(self.full, "nope/r1", "x")
        runner.invalidate(self.full, passed["trial_id"], "grader bug found in review")
        s = summary(self.full)
        row = next(r for r in s["trials"] if r["trial_id"] == passed["trial_id"])
        self.assertEqual((row["original_grade"], row["grade"]), ("PASS", "INVALID"))
        cfg = passed["trial_id"].split("/")[0]
        self.assertEqual(by_config(s, "grades")[cfg]["PASS"], before[cfg]["PASS"] - 1)
        self.assertIn(passed, lines(self.full))  # the original grade record is untouched


if __name__ == "__main__":
    unittest.main()
