# AB5-05a - real task `real-001`

Status: draft. Track: **transparent diagnostic** (host grading of authored reference patches only; untrusted
candidates need the qualified target of AB5-05b). Grader: `patch-io` v1.

## Choice

Real fix from a public repository, gradable inside the AB5-05b boundary (stdlib Python, no network, small):
agent-harness commit `2ada5ff` "fix(contract): require integer units for complete usage" (2026-10-05, MIT).
Showcase tasks were not used: Java/Gradle needs dependency downloads and more memory than B5/B8 allow; S30-06 is
excluded by the plan. Contamination: the repository is public, so a model with browsing or later training data may
have seen the fix; this is recorded in `task.json` `provenance`.

## Bundle `tasks/real-001`

`base/` = agent-harness at `af994d7` (parent of the fix) without `.github`, incl. `LICENSE`. Scope:
`src/agent_harness/contract.py`, `src/agent_harness/contract_fixtures/success.json` (the files the real fix
changed under `src/`); tests are out of scope. Visible check: `PYTHONPATH=src python -m unittest
tests.test_contract tests.test_boundaries` (the packaging tests need an installed package and are not task checks).
Hidden: 6 `validate_result` calls (`hidden/cases.json`, inputs only) with expected value or `ContractError`
(`expected/expected.json`): integer units under `complete` valid; null cache/input units under `complete` rejected;
missing summary under `complete` rejected; null units under `partial` valid; `unknown` without events valid.
Reference patches: `good` (the real src diff), `noop`, `wrong` (checks null units only), `overstrict` (rejects
null units under every completeness), `test_deletion`.

## AC -> evidence (`tests/test_real_task.py`)

| AC | Test |
|---|---|
| base fails, real fix passes | `test_real_fix_passes`, `test_base_and_partial_or_overstrict_fixes_fail_on_behaviour` (noop) |
| partial / over-strict fixes fail on behaviour | `test_base_and_partial_or_overstrict_fixes_fail_on_behaviour` |
| test manipulation | `test_test_deletion_is_out_of_scope` |
| bundle pinned and complete | `test_bundle_matches_pinned_digests`, `test_visible_checks_pass_on_base` |
| end to end through the fake runner | `test_fake_run_grades_reference_patches` |

# Real task `real-002`

Harder than `real-001`: two independent gaps in agent-harness contract v2, one of them an equality-versus-type trap.
Source: agent-harness commit `b29dfdf` "fix(contract): exact applied limits, explicit limits for qualified requests,
backend targets" (2026-10-07, MIT); base = parent `f2eeda2` (without `.github`). Scope:
`src/agent_harness/contract.py` (the commit's `execution.py` change is out of scope). Visible check:
`PYTHONPATH=src python -m unittest tests.test_contract tests.test_contract_v2 tests.test_boundaries`.

Hidden: 9 cases. `validate_request`: qualified without limits rejected; qualified with limits and plain without
limits valid. `validate_result`: exact applied valid; `True` for a limit of 1, a float limit, a float timeout, an
extra key and a different value rejected. The base fails 4 of them. Reference patches: `good` (real fix), `noop`,
`request_only`, `applied_only` (each half), `overstrict` (limits required on every v2 request), `test_deletion`.

| AC | Test (`tests/test_real_task.py`, `RealTask2`) |
|---|---|
| base fails, real fix passes | `test_real_fix_passes`, `test_base_half_and_overstrict_fixes_fail_on_behaviour` |
| each half fix and an over-strict fix fail on behaviour | `test_base_half_and_overstrict_fixes_fail_on_behaviour` |
| test manipulation | `test_test_deletion_is_out_of_scope` |
| bundle pinned and complete | `test_bundle_matches_pinned_digests`, `test_visible_checks_pass_on_base` |
| end to end through the fake runner | `test_fake_run_grades_reference_patches` |

Agent run: `experiments/real-002.json` (same configs as the AB5-07 pilot, 4 repetitions each).
