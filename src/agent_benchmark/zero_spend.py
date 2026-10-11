"""Zero-spend preflight for subscription CLIs (AB5-07): nothing may route a trial to pay-per-token billing.

Reads the environment and the CLIs' local login status; for OpenCode configs also the OpenRouter key file and
`GET https://openrouter.ai/api/v1/key` (the key's credit limit must be 0). No model call. The harness enforces the
fixed CLI flags and refuses non-`:free` OpenRouter models at launch as well.
"""
import json
import os
import subprocess
import urllib.request
from pathlib import Path

# Each of these makes Claude Code or Codex bill an API account instead of the subscription.
BILLING_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
               "CODEX_API_KEY", "CODEX_ACCESS_TOKEN")


OPENROUTER_KEY_FILE = Path.home() / ".config" / "agent-benchmark" / "openrouter.key"


def _openrouter_key_info(key):
    req = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["data"]


def openrouter_problems(models, key_file=OPENROUTER_KEY_FILE, key_info=_openrouter_key_info):
    """Free OpenRouter models only, through a key that cannot spend: mode 600 and a credit limit of 0."""
    found = [f"opencode model {m!r} is not a :free model" for m in models if not m.endswith(":free")]
    try:
        if key_file.stat().st_mode & 0o077:
            return found + [f"{key_file} is readable by group or others; chmod 600 it"]
        key = key_file.read_text().strip()
    except OSError:
        return found + [f"no OpenRouter key file at {key_file}"]
    try:
        info = key_info(key)
    except Exception as exc:  # noqa: BLE001 - no proof of a zero-limit key, no run
        return found + [f"OpenRouter key check failed: {type(exc).__name__}"]
    if info.get("limit") != 0:
        found.append(f"OpenRouter key credit limit is {info.get('limit')!r}, not 0: it could spend money")
    return found


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
