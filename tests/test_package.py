"""AB5-00: import has no side effects / network use; CLI help works from an empty cwd without API keys."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC = str(Path(__file__).resolve().parents[1] / "src")
GUARD = (
    "import socket\n"
    "def deny(*a, **k): raise RuntimeError('network used at import')\n"
    "socket.socket.connect = deny; socket.create_connection = deny\n"
)


def clean_env():
    env = {k: v for k, v in os.environ.items() if "API_KEY" not in k and "TOKEN" not in k}
    env["PYTHONPATH"] = SRC
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


class Package(unittest.TestCase):
    def test_import_has_no_side_effects(self):
        code = GUARD + "import agent_benchmark, agent_benchmark.cli, agent_benchmark.runner, agent_benchmark.report\n"
        with tempfile.TemporaryDirectory() as d:
            p = subprocess.run([sys.executable, "-c", code], cwd=d, env=clean_env(), capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual((p.stdout, p.stderr), ("", ""))
            self.assertEqual(os.listdir(d), [])

    def test_help_from_empty_cwd(self):
        with tempfile.TemporaryDirectory() as d:
            for args in ([], ["validate"], ["run"], ["report"]):
                p = subprocess.run([sys.executable, "-m", "agent_benchmark", *args, "--help"], cwd=d,
                                   env=clean_env(), capture_output=True, text=True)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertIn("usage: agent-benchmark", p.stdout)

    def test_invalid_manifest_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "m.json").write_text('{"schema_version": "nope"}')
            p = subprocess.run([sys.executable, "-m", "agent_benchmark", "validate", "m.json"], cwd=d,
                               env=clean_env(), capture_output=True, text=True)
            self.assertEqual(p.returncode, 2)
            self.assertIn("unsupported", p.stderr)


if __name__ == "__main__":
    unittest.main()
