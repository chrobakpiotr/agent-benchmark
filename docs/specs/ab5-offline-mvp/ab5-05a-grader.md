# AB5-05a - deterministic task bundle and patch grader

Status: draft. Track: **transparent diagnostic**, not hidden grading.

## Bundle `tasks/reference-001`

Synthetic task (fix `calc.median`), chosen per plan: grading is validated on a small synthetic task first; a real
task is picked after the Showcase review. S30-06 is not used. Layout: `task.json`, `base/` (workspace incl. visible
tests), `hidden/` (grader tests), `reference/*.patch` (known-good and known-bad candidates used by the fake
executor). `task.json` pins `base/` and `hidden/` with `tree_digest` (sorted path + file digest; symlinks refused),
`scope` (paths a patch may touch), exact `hidden_test_count` and `timeout_seconds`. The manifest pins `task.json`.
The run directory gets a copy of the whole bundle (`run/task/`).

## Grader `patch-unittest` v1

1. candidate bytes must match the sealed digest, else INVALID;
2. `base/` and `hidden/` must match pinned digests, else INVALID (grader inputs cannot be edited by the executor);
3. host execution only when the caller vouches for the candidate source (`executor.kind == "fake"`), else INVALID;
4. every touched path must be in `scope`: no absolute, `..`, symlink mode, tests or new files such as
   `sitecustomize.py`, else FAIL (patch is never applied);
5. `git apply` on a fresh copy of `base/`, else FAIL (`bad_base`, `malformed`);
6. `hidden/` is copied next to (not into) the workspace after the patch, run with `python -m unittest` in a new
   process group with an empty env (no secrets) and a timeout; on timeout the group is killed, FAIL;
7. PASS only if exit code 0 **and** the run count equals `hidden_test_count` (multiplicity, not just "green").

Criteria with details (pinned digests, run count, exit code, output digest) are stored in the grade record.

## AC -> evidence (`tests/test_reference_task.py`)

| AC | Test |
|---|---|
| base fails, known-good passes, no-op/wrong/hardcoded fail | `test_known_good_passes`, `test_base_noop_wrong_hardcoded_fail_on_behaviour` |
| test manipulation / test deletion | `test_test_deletion_and_escape_are_out_of_scope`, `test_import_hijack_and_hidden_test_edit_are_out_of_scope` |
| grader timeout | `test_hanging_candidate_is_killed` |
| wrong patch / base | `test_wrong_base_and_malformed_do_not_apply` |
| escape outside workspace | `test_test_deletion_and_escape_are_out_of_scope`, hijack test (`../hidden`, `/etc/passwd`) |
| grader inputs not modifiable, digest evidence | `test_tampered_bundle_is_invalid`, `test_bundle_matches_pinned_digests` |
| multiplicity enforced | `test_hidden_test_multiplicity_is_enforced` |
| grading without secrets; none in run records | `test_candidate_runs_without_the_callers_secrets` (canary env), `ReferencePipeline.test_no_secret_reaches_run_records` |
| end to end through the fake runner | `ReferencePipeline.test_fake_run_grades_reference_patches` |

## Limits (AB5-05b)

No CPU/memory/network limits and no filesystem sandbox: candidate code runs as the current user. Hidden tests are
readable in the bundle. Process-group kill on timeout is implemented but has no test with a forking candidate.
Model-generated patches must not be graded here until a qualified isolated grading host exists.
The verdict (exit code + `Ran N tests`) comes from the process that imports the candidate: an in-scope patch
that prints `Ran 4 tests` and exits 0 at import gets PASS (verified 2026-10-06). PASS is therefore valid only for
authored reference patches; the fix (verdict computed outside the candidate's process) is in `ab5-05b-grading-boundary.md`.
