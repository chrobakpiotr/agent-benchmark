"""AB5-01: manifest/task/event validation and frozen fixture round-trip. No models, no network."""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_benchmark.schema import (ValidationError, canonical, digest, load_manifest, validate_event,  # noqa: E402
                                    validate_manifest, validate_task)

FIXTURES = Path(__file__).parent / "fixtures"
MANIFEST = FIXTURES / "manifest-offline-001.json"
TASK = FIXTURES / "tasks/synthetic-sort-001/task.json"


def base():
    return json.loads(MANIFEST.read_text())


class ManifestValidation(unittest.TestCase):
    def rejects(self, mutate, match):
        m = base()
        mutate(m)
        with self.assertRaisesRegex(ValidationError, match):
            validate_manifest(m, digest(TASK.read_bytes()))

    def test_fixture_is_valid(self):
        m, task, _, _ = load_manifest(MANIFEST)
        self.assertEqual(m["experiment_id"], "offline-001")
        self.assertEqual(task["task_id"], "synthetic-sort-001")

    def test_unknown_version(self):
        self.rejects(lambda m: m.update(schema_version="agent-benchmark/manifest/v2"), "unsupported")

    def test_missing_identity(self):
        self.rejects(lambda m: m.pop("experiment_id"), "missing fields")
        self.rejects(lambda m: m["configs"][0].update(config_id=""), "non-empty string")
        self.rejects(lambda m: m["configs"][0].pop("model_resolved"), "explicit null")

    def test_wrong_bindings(self):
        self.rejects(lambda m: m["executor"]["script"][0].update(config_id="cfg-x"), "unknown config")
        self.rejects(lambda m: m["executor"]["script"][0].update(repetition=4), "repetition")
        self.rejects(lambda m: m["task"].update(digest="sha256:" + "0" * 64), "binding mismatch")

    def test_contradictory_values(self):
        self.rejects(lambda m: m["configs"].append(copy.deepcopy(m["configs"][0])), "duplicate config_id")
        self.rejects(lambda m: m["executor"]["script"][0].update(candidate=None), "without a candidate")
        self.rejects(lambda m: m["executor"]["script"][0]["usage"].update(output_tokens=None), "contradicts null")
        self.rejects(lambda m: m["executor"]["script"][1].update(config_id="cfg-a", repetition=1), "duplicate script")
        self.rejects(lambda m: m["executor"]["script"].pop(), "no scripted outcome")
        self.rejects(lambda m: m["configs"][0].update(isolation_track="hidden"), "fake executor requires")
        self.rejects(lambda m: m.update(repetitions=0), "repetitions")
        self.rejects(lambda m: m["executor"]["script"][0].update(outcome="succeeded"), "outcome")
        self.rejects(lambda m: m.update(exclusions=["infra"]), "exclusions")
        self.rejects(lambda m: m["retry_policy"].update(max_attempts=3), "max_attempts")

    def test_unknown_fields_rejected(self):
        self.rejects(lambda m: m.update(extra=1), "unknown fields")

    def test_unknown_usage_is_valid(self):
        m = base()
        for e in m["executor"]["script"]:
            e["usage"] = None
        validate_manifest(m, digest(TASK.read_bytes()))

    def test_round_trip_is_stable(self):
        m = load_manifest(MANIFEST)[0]
        once = canonical(m)
        self.assertEqual(canonical(validate_manifest(json.loads(once))), once)


class TaskValidation(unittest.TestCase):
    def test_invalid_grader_rejected(self):
        t = json.loads(TASK.read_text())
        t["grader"]["id"] = "trust-me"
        with self.assertRaisesRegex(ValidationError, "unknown grader"):
            validate_task(t)

    def test_grader_version_mismatch_rejected(self):
        t = json.loads(TASK.read_text())
        t["grader"]["version"] = "2"
        with self.assertRaisesRegex(ValidationError, "unknown grader"):
            validate_task(t)

    def test_edited_task_breaks_binding(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(FIXTURES, d, dirs_exist_ok=True)
            task = Path(d) / "tasks/synthetic-sort-001/task.json"
            task.write_text(task.read_text().replace("[3, 1, 2, 3, -5]", "[1]"))
            with self.assertRaisesRegex(ValidationError, "binding mismatch"):
                load_manifest(Path(d) / "manifest-offline-001.json")


class EventValidation(unittest.TestCase):
    def test_unknown_event_version_and_type(self):
        with self.assertRaisesRegex(ValidationError, "unsupported"):
            validate_event({"schema_version": "agent-benchmark/event/v0", "type": "grade"}, "e")
        with self.assertRaisesRegex(ValidationError, "unknown event type"):
            validate_event({"schema_version": "agent-benchmark/event/v1", "type": "victory"}, "e")


if __name__ == "__main__":
    unittest.main()
