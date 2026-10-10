# AB5-07 - zero-spend live pilot

Status: draft; blocked on a harness backend that runs agent CLIs in the qualified sandbox (see "Dependencies").
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

Open: Claude's permission mode. `acceptEdits` auto-accepts edits but presumably denies shell commands in `-p`
(UNVERIFIED), so Claude could not run tests while Codex can (`workspace-write` allows sandboxed commands). Parity
needs shell allowed under Claude Code's own sandboxed Bash with network off; `bypassPermissions` would let commands
read the mounted login token. Decide with the harness backend; until then the row is provisional.

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

## Procedure

1. One calibration trial per config; read the quota bar (`/usage`, Codex `/status`) before and after.
2. Schedule the remaining 4 per config across 5-hour windows; never while the maintainer's Claude Code session is
   active (shared Pro quota). OpenRouter at most about 1 trial per day (50 requests/day).
3. Report per config: PASS rate (Wilson), wall time, tokens, quota windows used, every failure/timeout/limit.
   Two configs x 5 trials checks the process; it is not a ranking.

## Dependencies

- Harness: backend that runs the CLI inside the qualified target, with network only to the provider, the
  subscription login token mounted read-only in the execution phase only, no API-key variables, and usage from the
  CLI's JSON output in the result (requested 2026-10-10).
- Grading: `patch-io` on the qualified target (AB5-05b), not on this host.
