# AB5-07 - zero-spend live pilot

Status: execution path implemented on harness v0.6.0 (AH5-05b `AgentCliBackend`); grading of agent-written
candidates blocked on harness AH5-04c (`patch-io` on the qualified target).
Budget: **zero money**. Only the user's existing subscriptions (Claude Pro, ChatGPT Plus) and free OpenRouter models;
no API keys, no usage credits, no credit purchases.

## Facts this plan relies on (checked 2026-10-10 against vendor docs)

- `claude -p` logged in via claude.ai draws from the Pro 5-hour and weekly limits, shared with claude.ai and with
  any Claude Code session (including the one maintaining this repo). `ANTHROPIC_API_KEY` or `--bare` bypass the
  subscription. Pro's default model in Claude Code is Opus 5.5; Fable and 1M-context models need usage credits.
  `total_cost_usd` is a client-side list-price estimate, not a charge.
- `codex exec` logged in with ChatGPT draws from the Plus 5-hour window and weekly cap, shared with ChatGPT.
  `CODEX_API_KEY` (not `OPENAI_API_KEY`) switches it to API billing. `--json` reports cumulative thread usage on
  `turn.completed` (`input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens`,
  `reasoning_output_tokens`).
- OpenRouter `:free` models: 20 requests/min, 50 requests/day without purchased credits (failed requests count);
  the free list rotates. Usable today with tools: `cohere/north-mini-code:free`.
- Not used: Gemini CLI personal login (ended 2026-06-18), GitHub Models (retired 2026-07-30), Groq/Cloudflare
  free tiers (token caps below one trial), local models (Intel CPU-only, 2-5 tokens/s, hours per trial).

## Configurations (task `real-001`, 5 repetitions each, sequential)

| config | CLI | model | flags | isolation_track |
|---|---|---|---|---|
| `claude-sonnet-pro` | Claude Code (pinned version) | `sonnet` | `-p --output-format json --model sonnet --permission-mode acceptEdits` | qualified target |
| `codex-sol-plus` | Codex CLI (pinned version) | `gpt-6.1-sol` | `exec -m gpt-6.1-sol --sandbox workspace-write --skip-git-repo-check --json --ephemeral` | qualified target |
| `openrouter-free` (optional) | agent CLI to be chosen (OpenCode/Aider) | `cohere/north-mini-code:free` | headless single task | qualified target |

Both CLIs get equal conditions (harness AH5-05b, smoke-tested on this host): Claude Code's Bash runs in its own
sandbox with no network (`failIfUnavailable`, no unsandboxed commands, WebFetch/WebSearch disallowed, CLI login
directories unreadable); Codex runs `--sandbox workspace-write`; neither falls back to another mode. The prompt goes in
on stdin; API-billing variables are removed from the child; login methods are pinned (`claudeai`, `chatgpt`); a
candidate or output containing a login token or credential shape is withheld (`error`/`PROVIDER_ERROR`).

CLI name and version, model, flags and permissions are part of the config identity (`cli`, `cli_version`,
`tool_permissions`, `workflow`); changing any of them, e.g. a different Codex sandbox mode, is a new config.

## Zero-spend rules

1. `agent-benchmark preflight` must pass before every run: no `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`,
   `CLAUDE_CODE_USE_BEDROCK/VERTEX`, `CODEX_API_KEY`, `CODEX_ACCESS_TOKEN`; Claude logged in via claude.ai;
   Codex logged in via ChatGPT. (Implemented: `src/agent_benchmark/zero_spend.py`.)
2. At launch (to implement with the backend): refuse `--bare`; refuse Codex sandbox modes other than
   `workspace-write`; refuse OpenRouter model ids without `:free`.
3. Account settings (user, verified 2026-10-10): Claude usage credits off; ChatGPT/Codex credit auto-reload off,
   credit balance 0; ChatGPT Computer history off.
4. Quota exhausted -> the trial ends as reported by the backend and the run stops; no paid fallback, no automatic
   extra trials. Remaining trials continue in a later window via `resume`.
5. Cost is reported as `subscription, not priced` with token counts; never priced from API list prices.
   `total_cost_usd` may be shown only labelled as a list-price estimate.

## Implementation (`experiments/ab5-07-pilot.json`, `runner.agent_cli_execute`)

- Executor kind `agent-cli`, configs name their `cli` (`claude`/`codex`), track `controlled-host`.
- Per trial: a fresh workspace `<run>/workspaces/<request_id>` (copy of the task base, one Git base commit); prompt =
  task description + visible checks (`harness_port.agent_prompt`, nothing hidden); `AgentCliBackend(cli, prompt,
  diff_base=<base commit>)`; candidate = the diff the harness seals after `drain: confirmed`.
- Before every run and resume: `zero_spend.problems()` must be empty and the run directory must not be inside
  `/tmp` or `$TMPDIR` (the harness refuses agent-writable evidence roots).
- Agent-written candidates are recorded but **ungraded** (no grade event) until the qualified grading target exists;
  the report banner says so. Refusal reasons and withheld outputs are kept in `backend-notes.json`.
- Evidence: `tests/test_agent_cli_run.py` (fake `codex`/`claude` on `PATH`, no provider call).

## Procedure

1. `agent-benchmark run experiments/ab5-07-pilot.json --out ~/agent-benchmark-runs/<name>` (outside `/tmp`).
   One calibration trial per config first; read the quota bar (`/usage`, Codex `/status`) before and after.
2. Schedule the remaining 4 per config across 5-hour windows; never while the maintainer's Claude Code session is
   active (shared Pro quota). OpenRouter at most about 1 trial per day (50 requests/day).
3. Report per config: PASS rate (Wilson), wall time, tokens, quota windows used, every failure/timeout/limit.
   Two configs x 5 trials checks the process; it is not a ranking.

## Dependencies

- Harness: backend that runs the CLI inside the qualified target, with network only to the provider, the
  subscription login token mounted read-only in the execution phase only, no API-key variables, and usage from the
  CLI's JSON output in the result (requested 2026-10-10).
- Grading: `patch-io` on the qualified target (AB5-05b), not on this host.
