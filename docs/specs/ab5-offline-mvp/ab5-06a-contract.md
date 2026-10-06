# AB5-06a - consume the agent-harness execution contract v1

Status: draft. Scope: everything in AB5-06 that does not need a launch API. Harness-launched execution is AB5-06b
(depends on AH5-03b).

## Changes

- Dependency on `agent-harness` pinned to commit `e57fda8` (tag `v0.1.0`); details in `docs/execution-port.md`.
- `harness_port.py`: contract request building, fake backend returning contract results, result import.
- Formats (no persisted data in older versions existed):
  - manifest v2: script `completion` (`accepted/rejected/null`) instead of `harness_completion`; script usage is
    `{units, cache_semantics}`; outcome `rejected`; `budget.max_wall_seconds` required (contract
    `timeout_seconds`); `config_id` restricted to contract ID characters without `/`; `max_attempts` 1..100.
  - event v3: `trial_started.request_digest`; terminal adds `exit_code`, `completion`, `error_code`, `drain`,
    `isolation_level`, `resolved_model`, attempt times; usage events carry `source`, `units` (incl.
    `cache_write_tokens`) and `cache_semantics`.
  - pricing v2: `cache_write` rate; cache handling from usage `cache_semantics` instead of a pricing flag.
- A backend exception is now outcome `unknown` (launch state not known) instead of `error`.

## AC -> evidence (`tests/test_harness_port.py`)

| AC (plan AB5-06) | Evidence |
|---|---|
| public API only, pinned version | `Pin.test_only_public_contract_api_is_used`, `Pin.test_installed_contract_matches_pin` |
| contract fixtures from AH5-02 | `GoldenFixtures.*` (success, fail, timeout, unknown-terminal, missing-qualification from the installed wheel) |
| all child attempts and usage | `test_fail_is_completion_rejected_not_error` (2 attempts), `test_success` (summary over stream) |
| stale bindings / rejected launch | `test_contract_violation_never_becomes_success`, `test_timeout_unknown_and_rejected`, `test_rejected_counts_in_denominator_and_is_excludable` |
| no backend | `test_pipeline.test_backend_crash_is_recorded_as_unknown` |
| candidate reference verified | `test_candidate_reference_is_verified_before_sealing` |
| unsupported capabilities | contract `rejected` with `CAPABILITY_UNSUPPORTED/NOT_QUALIFIED` maps like `missing-qualification` |
| cancellation tied to real terminal/drain | covered in AB5-06b (`ab5-06b-launch.md`) |
