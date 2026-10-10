"""AB5-07: zero-spend preflight refuses anything that would bill an API instead of the subscriptions."""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_benchmark import zero_spend  # noqa: E402

CLAUDE_OK = json.dumps({"loggedIn": True, "authMethod": "claude.ai"})
CODEX_OK = "Logged in using ChatGPT\n"


def fake_run(claude=CLAUDE_OK, codex=CODEX_OK):
    def run(argv, **_):
        if argv[0] == "claude" and claude is None:
            raise FileNotFoundError(argv[0])
        return SimpleNamespace(stdout=claude if argv[0] == "claude" else codex, stderr="")
    return run


class Preflight(unittest.TestCase):
    def test_subscriptions_and_clean_env_pass(self):
        self.assertEqual(zero_spend.problems({"OPENAI_API_KEY": "x", "PATH": "/bin"}, fake_run()), [])

    def test_every_billing_variable_fails(self):
        for k in zero_spend.BILLING_ENV:
            found = zero_spend.problems({k: "x"}, fake_run())
            self.assertEqual(len(found), 1, k)
            self.assertIn(k, found[0])
        self.assertEqual(zero_spend.problems({"ANTHROPIC_API_KEY": ""}, fake_run()), [])  # empty = unset

    def test_api_key_logins_and_missing_cli_fail(self):
        cases = ((json.dumps({"loggedIn": True, "authMethod": "api_key"}), CODEX_OK, "claude"),
                 (json.dumps({"loggedIn": False}), CODEX_OK, "claude"),
                 ("not json", CODEX_OK, "claude"),
                 (None, CODEX_OK, "claude"),
                 (CLAUDE_OK, "Logged in using an API key\n", "codex"),
                 (CLAUDE_OK, "Not logged in\n", "codex"))
        for claude, codex, who in cases:
            found = zero_spend.problems({}, fake_run(claude, codex))
            self.assertEqual(len(found), 1, (claude, codex))
            self.assertTrue(found[0].startswith(who), found)


if __name__ == "__main__":
    unittest.main()
