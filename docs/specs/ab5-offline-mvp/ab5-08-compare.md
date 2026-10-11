# AB5-08 - comparison of two experiments

Status: draft. `agent-benchmark compare RUN_A RUN_B [--out FILE]` (`src/agent_benchmark/compare.py`), built only
from recorded files (`load_run`, `summarize`, `evidence/*/result.json` `versions`). Read-only: nothing is executed or
written into either run.

## Behaviour

1. **Comparability first.**
   - Run-level reasons: task digest changed, grader identities changed, executor kind/track changed, execution
     backend versions changed.
   - Per config (matched by `config_id`): any change of `model_requested`, `cli`, `cli_version`, `prompt_digest`,
     `reasoning`, `sampling`, `tool_permissions`, `workflow`, `budget` or `isolation_track`.
   - A config present in one run only is not comparable.
   - Any reason makes the pair "not comparable", and no correctness or cost claim is made for it. A changed grader or
     task never yields "improved".
2. **Correctness before cost.**
   - Per comparable pair: PASS/denominator and Wilson 95% for both runs.
   - A difference ("B higher"/"B lower") is claimed only when the intervals do not overlap; otherwise "no evidence of
     a difference".
3. **Cost.** Compared only for comparable pairs with no PASS-rate difference, when both runs carry a pricing snapshot
   and both sides are fully priced in one currency. Otherwise the reason is stated. Subscription runs are never
   priced (AB5-07).
4. **Context.** Also shown: PASS duration median (wall time on the recording host) and tokens processed in/out
   (`usage.processed_input_tokens`, comparable across cache semantics).

## AC -> evidence (`tests/test_compare.py`)

| AC | Test |
|---|---|
| identical run configs are comparable | `test_identical_configs_are_comparable_and_overlapping_wilson_claims_nothing` |
| overlapping Wilson intervals claim no difference | same test (2/3 vs 2/3, 1/3 vs 1/3) |
| changed prompt / model alias detected per config | `test_changed_prompt_or_model_makes_only_that_config_not_comparable` |
| missing price does not compare cost | `test_pricing_on_one_side_only_is_not_a_cost_comparison` |
| changed task / grader never comparable | `test_changed_task_or_grader_is_never_comparable` |
| CLI output and unreadable run (exit 2) | `test_cli_prints_markdown_and_rejects_unreadable_runs` |

Not covered by a test: the "B higher/lower" branch. Fixtures with at most 3 trials per config always give overlapping
Wilson intervals.

## Pool and Fisher's exact test (2026-10-11)

- `agent-benchmark pool RUN...` groups runs by full identity (task, graders, executor, harness versions, the set of
  configs and each config's identity) and adds up every group separately, so argument order never selects a subset;
  the same run given twice (also through a symlink) is excluded. `--ignore-backend-version` drops harness versions
  from the identity and says so. CLI versions are part of the identity only when the manifest records `cli_version`.
- `compare` and `pool` report Fisher's exact two-sided p-value (stdlib `math.comb`) next to the Wilson intervals; the
  decision rule for "B higher/lower" stays non-overlapping Wilson intervals.
- Evidence: `test_fisher_exact_hand_computed` (Fisher's tea tasting 4/4 vs 0/4 -> 2/70), `test_pool_groups_by_identity_independent_of_order`, `test_pool_never_merges_a_differing_config_set_or_a_duplicate`.
