# AB5-07 - does pointing the instruction at the documentation help both agents? (pre-registered 2026-10-17, before any run)

Background: the check-related instruction raised Claude on both discriminating tasks (`ab5-07-prompt-addendum.md`).
It lowered Codex on `real-001-bug` from 16/20 to 3/20 (`ab5-07-prompt-addendum-codex.md`): Codex found the extra
inputs but chose the reading the contract rejects. Question: does a second sentence that says where the correct
behaviour comes from keep Claude's gain without hurting Codex?

## Fixed in advance

- Instruction v2 (config `prompt_addendum`): v1 plus one sentence, naming no case: "The report shows one example. The
  same underlying problem may show up with other inputs: before you finish, find them and make sure they are fixed
  too, without changing behaviour that was correct. Take the correct behaviour for those inputs from the project's
  documentation and contracts, not from a guess."
- Four runs, one per agent and task: `experiments/prompt-addendum-docs-{claude,codex}-{real-001-bug,real-012}.json`.
  Each run has two arms, interleaved: the pinned config without an addendum (same-run baseline) and
  `<config>-check-related-docs`. 15 repetitions per arm, 120 trials in total. Pinned `claude-sonnet-5-5` / CLI
  `2.1.289 (Claude Code)` and `gpt-6.1-sol` / `codex-cli 0.160.0`, harness v0.8.4.
- Predeclared exclusion: outcome `error`. Resumes after quota stops are allowed, and interim looks are disclosed.
- Primary analysis, once per run after all 30 trials: Fisher exact two-sided test, v2 arm vs same-run baseline,
  alpha 0.0125 per run (Bonferroni over four).
- Verdict "helps both" only if both Claude runs are significantly higher and neither Codex run is significantly
  lower. Each Codex run without a significant drop is reported as "no harm detected", not as "no harm".
- Secondary, descriptive: every FAIL is classified by the hidden case it fails. Median PASS duration ratio. v2 against
  v1 results from the earlier runs (different runs).
- Inconclusive for a run if an arm has fewer than 13 non-excluded trials.
- Power (Monte Carlo, 2000 draws, n = 15 per arm, alpha 0.0125): 41% for 0.15 -> 0.60, 86% for 0.15 -> 0.80; a Codex
  drop is detected with 50% probability for 0.80 -> 0.30, 86% for 0.80 -> 0.15, and 14% for 1.00 -> 0.70. Moderate
  harm to Codex can go undetected.

## Result (runs 2026-10-17, 120 trials)

| run | baseline PASS | v2 PASS | Fisher p | median PASS s baseline / v2 |
|---|---|---|---|---|
| Claude `real-001-bug` | 8/15 | 13/15 | 0.11 | 27.7 / 31.0 |
| Claude `real-012` | 3/15 | 8/14 (1 excluded, quota) | 0.060 | 37.9 / 47.2 |
| Codex `real-001-bug` | 12/15 | **0/15** | **1.1e-5** | 71.8 / n/a |
| Codex `real-012` | 15/15 | 14/14 (1 excluded, quota) | 1.0 | 55.8 / 136.5 |

Primary analysis (alpha 0.0125 per run): neither Claude run is significantly higher, and Codex on `real-001-bug` is
significantly lower. The verdict is therefore **not "helps both"**. Every arm has at least 13 non-excluded trials.
Descriptively, v2 helped Claude less than v1 (v1: 16/20 and 16/19), and Codex fell even further than with v1 (0/15).
On `real-012` there was no harm to Codex, but its trials took 2.4x longer.

Failures by hidden case:
- Every Codex v2 FAIL and every `real-001-bug` FAIL is `complete_without_summary`. Pointed at the documentation,
  Codex always took the stream-fallback reading that ADR 0002 permits (see the correction in `ab5-05a-real-task.md`).
- Claude's `real-012` FAILs miss `code_span_later_gt` and `code_span_trailing_slash`, as in the earlier runs.

The `real-001-bug` rows measure a reading preference, not correctness.

Deviations:
- Both Claude and Codex stopped on quota during `real-012` and were resumed after the reset.
- Two completed Claude `real-012` trials were left ungraded when they finished and were graded by a later `resume`
  (offline, same qualified target).
- Interim results of the `real-001-bug` runs were looked at before the `real-012` runs finished; the analysis was not
  changed.
