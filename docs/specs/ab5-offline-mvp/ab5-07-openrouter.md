# AB5-07 - third configuration: a free OpenRouter model (requirements)

Status: requirements; blocked on a harness backend for a third agent CLI. Budget: zero money.

## Facts (checked 2026-10-11)

- Free models with tool calling (OpenRouter `/api/v1/models`, no key needed): 14, among them
  `cohere/north-mini-code:free`, `nvidia/nemotron-3-super-120b-a12b:free`, `google/gemma-4-31b-it:free`;
  `poolside/laguna-*-2.1:free` expire 2026-10-31. The list rotates, so the model is pinned per run and checked
  before it.
- Free tier: 20 requests/minute, 50 requests/day while the account never bought credits (failed requests count).
  One agent trial needs about 20-80 requests, so about one trial per day; 4 trials take several days.
- OpenCode runs headless (`opencode run --format json`, prompt on stdin) with OpenRouter as a built-in provider
  (`openrouter/<vendor>/<model>`). It has **no OS-level sandbox**: its `permission` rules are command patterns
  (bypassable with `sh -c ...`, reported as not always enforced). Equal conditions with the other configs
  (sandboxed shell without network) therefore need a sandbox around it, not OpenCode settings.

## Requirements for the harness backend (proposal: `AgentCliBackend` provider `opencode`)

1. Fixed command line, prompt on stdin, `--format json`; model passed through and required to end in `:free`
   (refused before launch otherwise).
2. Shell commands run with no network, as for Claude/Codex. OpenCode itself needs HTTPS to `openrouter.ai` only.
   Options for the harness to choose: OpenCode inside a container whose only egress is an `openrouter.ai` proxy,
   or a host sandbox profile that allows network for the OpenCode process but not for its child shells. No
   fallback mode; a failed sandbox probe means `rejected` / `CAPABILITY_UNSUPPORTED`.
3. Credentials: the OpenRouter key (user-provided env var) reaches only OpenCode, never shell commands, and is
   scanned for in candidates/outputs like the other logins.
4. Usage from OpenCode's JSON events into one provider summary; unknown units stay null.
5. Errors: OpenRouter 429 (daily cap) maps to `error_details.kind = quota_exhausted` with `resets_at` (UTC
   midnight for the daily cap) so the benchmark stops and resumes the next day.

## Benchmark side (when the backend exists)

- Zero-spend preflight extension: `GET https://openrouter.ai/api/v1/key` with the user's key must report
  `"limit": 0` (a key created with a zero credit limit cannot spend, even if the account later holds credits), and
  the configured model id must end in `:free`; otherwise refuse. `is_free_tier` alone is not enough: per the docs it
  only means the all-time purchase is below the threshold. `free_model_daily_requests.remaining` is recorded before
  each trial, and a trial starts only with the full daily allowance left (right after the UTC reset).
- Feasibility risk: a trial cannot span days (a quota error ends it), so a trial that needs more than 50 requests can
  never complete on the free tier. The first calibration trial measures OpenCode's request count on `real-001`; if it
  exceeds 50, this configuration is dropped rather than paid for. Also to verify then: that a zero-limit key can call
  `:free` models.
- Config `openrouter-free`: `cli: "opencode"`, pinned model, track `controlled-host` (or the container track the
  harness provides), at most one trial per day; the run stops on quota and `resume` continues.

## User actions needed

- Approve installing OpenCode on this host (`npm i -g opencode-ai` or the harness-chosen method).
- Create an OpenRouter API key with credit limit 0 and buy no credits; it is passed only as an environment variable at run time,
  never written to the repository or logs.
