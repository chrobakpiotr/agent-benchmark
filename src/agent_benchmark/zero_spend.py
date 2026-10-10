"""Zero-spend preflight for subscription CLIs (AB5-07): nothing may route a trial to pay-per-token billing.

Reads only the environment and the CLIs' local login status; no model call. The CLI flags each trial uses
(`--bare`, sandbox mode, `:free` model ids) are checked where trials are launched, not here.
"""
import json
import os
import subprocess

# Each of these makes Claude Code or Codex bill an API account instead of the subscription.
BILLING_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
               "CODEX_API_KEY", "CODEX_ACCESS_TOKEN")


def _status(run, argv):
    try:
        p = run(argv, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"{argv[0]}: {type(exc).__name__}"
    return p.stdout + p.stderr, None


def problems(env=None, run=subprocess.run):
    """Reasons a trial could spend money; empty list = zero-spend preconditions hold."""
    env = os.environ if env is None else env
    found = [f"{k} is set: the CLI would bill the API instead of the subscription" for k in BILLING_ENV if env.get(k)]
    out, err = _status(run, ["claude", "auth", "status"])
    try:
        claude = json.loads(out) if out else {}
    except ValueError:
        claude = {}
    if err or not (claude.get("loggedIn") and claude.get("authMethod") == "claude.ai"):
        found.append(f"claude: not logged in with a Claude subscription ({err or claude.get('authMethod')})")
    out, err = _status(run, ["codex", "login", "status"])
    if err or "Logged in using ChatGPT" not in out:
        found.append(f"codex: not logged in with ChatGPT ({err or out.strip()[:80]})")
    return found
