# AB5-07 - zero-spend live pilot

Status: execution (AH5-05b `AgentCliBackend`) and grading (AH5-04c `QualifiedDockerBackend`) implemented on
harness v0.7.0.
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

## Configurations (task `real-001`, sequential; calibration 1 + pilot 4 repetitions each, separate runs)

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
4. Quota exhausted -> the trial ends as reported by the backend (`error`/`PROVIDER_ERROR`) and the run stops
   (implemented: `runner._execute` raises after any agent-cli `PROVIDER_ERROR`; only `completed` trials are graded); no paid fallback, no automatic
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
- Agent-written candidates are graded only on the qualified target: `harness_port.GradingSession` qualifies once
  per run directory (harness `qualification.qualify` under a fresh job id, matched against the independently reviewed
  tuple), then each candidate's patched workspace goes to `QualifiedDockerBackend` as a contract v2 request with
  `QUALIFIED_LIMITS`; `patch-io` computes the verdict on this host from the sealed `answers` artifact. The grade
  record's `isolation` holds target, job id, session/reviewed qualification digests, probe digest, image and the
  fired limit (B10). If the target does not qualify or refuses, candidates stay ungraded (never FAIL) and
  `resume` grades them later. Run with no other Docker load. Refusal reasons and withheld outputs are kept in `backend-notes.json`.
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

## Results (2026-10-11, zero spend)

Valid graded runs only (qualified grading; invalidated task-defect runs excluded, see `ab5-05a-real-task.md`):

| task | description | Claude Sonnet (Pro) | Codex gpt-6.1-sol (Plus) |
|---|---|---|---|
| `real-001` | spec | 5/5 | 5/5 |
| `real-002` | spec | 4/4 | 4/4 |
| `real-002-bug` | symptom | 4/4 | 4/4 |
| `real-003` | symptom | 2/2 completed | 4/4 |
| `real-005` v3 | symptom | 4/4 | 4/4 |
| `real-006` | symptom | 4/4 | 4/4 |
| `real-007` | symptom | 4/4 | 4/4 |
| `real-008` | symptom | 4/4 | 4/4 |
| `real-001-bug` v2 (3 runs) | symptom, unstated domain rule | 10/28, Wilson [0.21, 0.54] | 19/27 (+1 quota error), Wilson [0.52, 0.84] |
| builder/reviewer, `real-001-bug` v2 | symptom | Claude builds: 0/3 | Codex builds: 3/4 |

- Only `real-001-bug` discriminates. Correction (same day): on the operational denominator (10/28 vs 19/28, the
  Codex quota error counting as non-PASS) Fisher's exact test gives p = 0.032; the earlier p = 0.010 was a normal
  approximation on graded trials only (10/28 vs 19/27). The three runs span harness v0.7.0-v0.8.3, so this pooling uses
  `pool --ignore-backend-version`; the same-version runs alone (5/12 vs 9/12) give p = 0.21. Earlier text:
  a two-proportion test gives z = 2.57, p = 0.010; the conservative Wilson-overlap
  rule of `compare` does not yet declare a difference (overlap 0.515-0.542). Every failure on that task is the
  unstated "complete needs a summary for every attempt" rule.
- Claude is about 2.5-4x faster on every task. Local inferences (other regex groups, other exception paths, other
  entry points, well-known spec rules) were solved by both agents every time.
- The third configuration (OpenCode, free OpenRouter model) cannot finish a trial within the 50-requests/day free tier
  (see `ab5-07-openrouter.md`).
- This is one discriminating task with 28 trials per config: evidence about these two configurations on this task,
  not a general ranking.
