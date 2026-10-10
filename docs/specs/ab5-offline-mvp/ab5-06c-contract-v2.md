# AB5-06c - consume agent-harness contract v2 (target evidence and resource limits)

Status: draft. Builds on AB5-06b. Harness side: ADR 0005, tag `v0.5.0` (contract v2 since `v0.4.0`, candidate
targets added in `v0.5.0`).

## Changes

- Pin: `agent-harness` commit `16bb938` (tag `v0.5.0`); constitution text unchanged (1.0.1).
- Requests are contract v2. `build_request(..., limits=None)`: fake/scripted trials send `limits: null`
  (non-qualified, no target). Qualified launches will need explicit limits (contract rule); not wired before a
  qualified backend exists.
- `import_result` keeps the result `target` (`id`, `qualification_digest`, `image_digest`) and `limits`
  (`applied`, `fired`, `output_truncated`) in the terminal; both null for v1 results and fake runs.
- Event schema `agent-benchmark/event/v4`: `trial_finished` gains `target` and `limits` (nullable); `error_code`
  accepts `LIMIT_EXCEEDED`. v3 is rejected; no v3 data existed outside temporary test runs.
- Report: per config `limits_fired` counts by cause (`timeout/oom/pids/disk`, a column in the detail table), run
  `targets` (target ids seen; "none" for fake runs); CSV adds `limit_fired`, `target_id`. A limit-fired trial is a
  started trial: it stays in the operational-success denominator.

## AC -> evidence (`tests/test_harness_port.py`)

| AC | Evidence |
|---|---|
| pinned version, public API only, constitution copy | `Pin.test_installed_contract_matches_pin` (0.5.0, commit), `Pin.test_only_public_contract_api_is_used`, `Pin.test_constitution_is_an_exact_copy_of_the_pinned_one` |
| `LIMIT_EXCEEDED` kept with its cause and target | `GoldenFixtures.test_v2_limit_exceeded_keeps_cause_and_target` (harness fixture `v2-limit-exceeded`) |
| candidate target kept as unqualified | `GoldenFixtures.test_v2_candidate_target_stays_unqualified` (fixture `v2-candidate-target`) |
| v1 results still import | `GoldenFixtures.test_success`, `test_fail_is_completion_rejected_not_error`, `test_timeout_unknown_and_rejected` |
| fired limit through the runner, counted in the denominator, shown in the report | `RunnerOverContract.test_scripted_limit_fired_is_recorded_and_counted` (`ScriptedBackend(fired="oom")`) |
| fake runs carry no target and no limits | `RunnerOverContract.test_raw_contract_documents_are_kept_as_evidence` |
