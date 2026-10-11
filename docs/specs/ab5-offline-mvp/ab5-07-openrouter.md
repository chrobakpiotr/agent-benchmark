# AB5-07 - third configuration: a free OpenRouter model (requirements)

Status: integrated on harness v0.8.3 (`AgentCliBackend("opencode", ..., api_key_file=...)`); calibration on `real-001` pending. Budget: zero money.

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

## Verified on this host (2026-10-11)

- OpenCode 1.19.0 installed in `~/.local/bin/opencode` (`npm i -g --prefix ~/.local opencode-ai@1.19.0`; `/usr/local`
  is not writable and sudo was not used; the package's install scripts were not run). `opencode run` offers
  `--format json` and `-m provider/model`.
- The user's key lives in `~/.config/agent-benchmark/openrouter.key` (mode 600, directory 700), never in the repository
  or logs. `GET /api/v1/key`: `limit: 0`, `limit_remaining: 0`, `usage: 0`, `is_free_tier: true`, free-model daily
  requests 50.
- A zero-limit key can call `:free` models: one chat completion to `cohere/north-mini-code:free` returned
  `cost: 0` and `upstream_inference_cost: 0`; account `usage` stayed 0.

## Integration (harness v0.8.3)

- Manifest `cli: "opencode"`, model `vendor/model:free` (no `openrouter/` prefix); the runner passes
  `api_key_file=~/.config/agent-benchmark/openrouter.key` so the sandbox can deny reading it.
- Preflight for any config or reviewer using OpenCode: model ends in `:free`, key file mode 600, and
  `GET /api/v1/key` reports `limit: 0` (`zero_spend.openrouter_problems`, tests in `tests/test_zero_spend.py`).
- Claude/Codex runs can read the key file (only OpenCode's sandbox denies it); an OpenRouter key printed by them is
  still withheld by the harness's `\bsk-[A-Za-z0-9_-]{32,}` output pattern. A leak could not spend money (limit 0).
- Calibration: `experiments/opencode-calibration.json` (1 trial on `real-001`); the daily counter
  (`free_model_daily_requests.used`) is read before and after to measure the request count.
