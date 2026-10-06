# AB5-06b - launch trials through the agent-harness offline launch API

Status: draft. Builds on AB5-06a. Harness side: ADR 0004 (`agent_harness.execution`), tag `v0.2.0`.

## Changes

- Pin: `agent-harness` commit `43bb47c` (tag `v0.2.0`); `versions.agent-harness` in results reads `0.2.0`.
- `harness_port.launch(request, backend, evidence_root)` calls `execution.launch` with the trial evidence root as
  workspace and evidence root; no result within the request timeout + 60 s cancels it and the trial is `unknown`.
- `harness_port.fake_backend` removed; `scripted_backend(entry, candidate)` maps a script entry to the harness
  `ScriptedBackend` (scripted `rejected` -> `rejection="BACKEND_UNAVAILABLE"`, `error` -> `PROVIDER_ERROR`). The
  harness seals the candidate under `executions/` in the evidence root; `import_result` verifies it as before.
- `build_request(..., capabilities=("usage",))`: a request lists the capabilities the trial needs.
- Relaunching a `request_id` returns the harness's stored result (or `unknown` after a crash); `resume` never
  relaunches an ID, replacements get a new one, so behaviour is unchanged.
- `ProcessBackend` is not wired into the runner (no live or process trials before AB5-07); any caller passes an
  explicit minimal `env`.

## AC -> evidence (`tests/test_harness_port.py`)

| AC (plan AB5-06) | Evidence |
|---|---|
| public API only, pinned version | `Pin.test_only_public_contract_api_is_used`, `Pin.test_installed_contract_matches_pin` (0.2.0, commit) |
| launched by the harness, candidate sealed by it | `test_candidates_are_sealed_by_the_harness`, `test_raw_contract_documents_are_kept_as_evidence` |
| all child attempts and usage | `test_cost.ReportCost.test_retries_cache_and_zero_pass` (2 scripted attempts through `launch`) |
| rejected launch | `test_rejected_counts_in_denominator_and_is_excludable` (`BACKEND_UNAVAILABLE`, nothing written) |
| capabilities propagated | `ProcessLaunch.test_unsupported_capability_is_rejected_without_launch` |
| cancellation tied to real terminal/drain | `ProcessLaunch.test_cancel_resolves_to_a_real_terminal_with_drain` (real `sleep`, `controlled`, not qualified) |
