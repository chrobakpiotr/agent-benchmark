# AB5-07 - does the check-related instruction also help Codex? (pre-registered 2026-10-14, before any run)

Question: on `real-001-bug` v2 Codex passed 25/47 without any instruction. With the instruction, Claude passed 16/19
(`ab5-07-prompt-addendum.md`). Does the same instruction raise Codex's PASS rate? `real-012` is left out because Codex
already passed it 20/20.

## Fixed in advance

- Manifest `experiments/prompt-addendum-codex-real-001-bug.json`: two Codex arms interleaved in one run.
  `codex-sol-pinned` has no addendum and is the same-run baseline. `codex-sol-pinned-check-related` uses the
  addendum, worded exactly as in the Claude experiment. 20 repetitions per arm; pinned `gpt-6.1-sol`, CLI
  `codex-cli 0.160.0`, harness v0.8.4.
- Predeclared exclusion: outcome `error`. Resumes after quota stops are allowed; interim looks are disclosed.
- Primary analysis, once after all 40 trials: Fisher exact two-sided test, addendum arm vs same-run baseline,
  alpha 0.05. Secondary, descriptive only: median PASS duration ratio, and the addendum arm against Claude's
  addendum arm (different run).
- Inconclusive if an arm has fewer than 18 non-excluded trials.
- Power (Monte Carlo, 2000 draws, baseline 0.53, n = 20 per arm): 35% for 0.80, 67% for 0.90, 99% for 1.00. A
  non-significant result is not evidence that the instruction does nothing for Codex.

## Result (run 2026-10-14, 40 trials)

| arm | PASS / non-excluded | excluded | Wilson 95% | median PASS s |
|---|---|---|---|---|
| `codex-sol-pinned` (baseline) | 16/20 | 0 | [0.584, 0.919] | 87.5 |
| `codex-sol-pinned-check-related` (addendum) | 3/20 | 0 | [0.052, 0.360] | 86.2 |

Primary analysis: Fisher exact two-sided p = 8.8e-5 < 0.05, but in the opposite direction from the question: on this
task the instruction **lowered** Codex's PASS rate. Both arms have 20 non-excluded trials.

Every FAIL in both arms fails the same hidden case, `complete_without_summary`. That result has
`usage_completeness: "complete"` and stream events with integer units, but no summary event, so the contract rejects
it. In the failing candidates, a missing summary falls back to the attempt's stream events, so that result is
accepted. Candidates whose added lines mention stream events:

| arm | PASS with / without stream logic | FAIL with / without stream logic |
|---|---|---|
| baseline | 3 / 13 | 4 / 0 |
| addendum | 1 / 2 | 17 / 0 |

Asked to look for other inputs with the same problem, Codex nearly always went on to define completeness for results
without a summary. It chose the reading the contract rejects. The instruction widened the search but did not
supply the rule.

Secondary, descriptive: the baseline's 16/20 is above Codex's confirmatory 25/47 (different run, different day).
Claude with the addendum passed 16/19. The instruction did not change Codex's time.
Deviations: none. The run finished without a stop; no interim look was taken.

## Correction (2026-10-17)

The `complete_without_summary` case has a second plausible reading that no reference patch covers. Its input has `usage_completeness: "complete"` and one `stream` event with integer units and no `summary`. ADR 0002 in the base says only that a summary, *if present*, is authoritative and that stream events are informational. Neither the base code nor its docs say that `complete` requires a summary. "Without a summary, the stream events are the usage" is therefore consistent with the docs, and patches that read it that way fail this case. Every real-001-bug FAIL in every run fails exactly this case. The result above therefore shows how often each arm chose the reading the task's hidden case expects (the
upstream fix's reading). It does not show correctness. See `ab5-05a-real-task.md`.
