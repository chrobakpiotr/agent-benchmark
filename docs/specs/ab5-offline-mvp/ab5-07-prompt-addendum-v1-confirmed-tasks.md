# AB5-07 - the check-related instruction on both confirmed tasks (pre-registered 2026-10-18, before any run)

Question: on the two confirmed discriminating tasks (`real-001-bug` v3, `real-012`), does the v1 check-related
instruction (`ab5-07-prompt-addendum.md`) close Claude's gap without hurting Codex? Already measured: Claude on
`real-012` went from 2/19 to 16/20. The post-hoc re-grade of v2 candidates against v3 suggests Claude 32/34 and Codex
35/35 with the instruction. Those numbers come from v2 trials and motivate this test, but do not count as evidence.

## Fixed in advance

- Instruction: v1, worded exactly as before.
- Three runs, each with two interleaved arms: the pinned config without an addendum (same-run baseline) and
  `<config>-check-related`.
  - `experiments/prompt-addendum-v1-claude-real-001-bug-v3.json`: 20 repetitions per arm.
  - `experiments/prompt-addendum-v1-codex-real-001-bug-v3.json`: 15 repetitions per arm.
  - `experiments/prompt-addendum-v1-codex-real-012.json`: 15 repetitions per arm.
  - 100 trials in total. Pinned `claude-sonnet-5-5` / CLI `2.1.289 (Claude Code)` and `gpt-6.1-sol` /
    `codex-cli 0.160.0`, harness v0.8.4.
- Predeclared exclusion: outcome `error`. Resumes after quota stops are allowed; interim looks are disclosed.
- Primary analysis, once per run after all its trials: Fisher exact two-sided test, addendum arm vs same-run
  baseline, alpha 0.0167 per run (Bonferroni over three).
- Verdict "closes the gap without hurting Codex" only if both of these hold:
  - the Claude run is significantly higher;
  - neither Codex run is significantly lower.
- A Codex run without a significant drop is reported as "no harm detected", not as "no harm".
- Secondary, descriptive: FAILs by hidden case, and median PASS duration ratio.
- Inconclusive for a run if an arm has fewer than 13 non-excluded trials (18 for the Claude run).
- Power (Monte Carlo, 2000 draws, alpha 0.0167):
  - Claude, n = 20 per arm: 87% for 0.35 -> 0.90, 44% for 0.35 -> 0.75.
  - Codex, n = 15 per arm: a drop from 1.00 is detected with 13% probability at 0.70 and 71% at 0.50.
  - Moderate harm to Codex can go undetected.

## Result (runs 2026-10-18, 100 trials)

| run | baseline PASS | with instruction | Fisher p | median PASS s baseline / instruction |
|---|---|---|---|---|
| Claude `real-001-bug` v3 | 7/20 | **19/20** | **1.4e-4** | 25.3 / 26.9 |
| Codex `real-001-bug` v3 | 15/15 | 15/15 | 1.0 | 68.6 / 75.2 |
| Codex `real-012` | 15/15 | 14/14 (1 excluded, quota) | 1.0 | 81.9 / 140.6 |

Primary analysis (alpha 0.0167 per run): the Claude run is significantly higher, and neither Codex run is lower. The
verdict is therefore **"closes the gap; no harm to Codex detected"**. Every arm has at least the required number of
non-excluded trials.
Secondary:
- Claude's baseline FAILs: 11 on `complete_summary_overrides_null_stream` and 2 on
  `complete_stream_only_null_cache_read`. The one FAIL with the instruction is the override case.
- On `real-012` Codex took 1.7x longer with the instruction; on `real-001-bug` v3, 1.1x.
- Together with Claude on `real-012` (2/19 -> 16/20), the instruction lifted Claude to Codex's level on both confirmed
  tasks.
Deviations:
- The Codex `real-012` run stopped on quota after 9 trials. A delayed resume scheduled for the reset did not fire
  while the host slept, so the run was resumed by hand at 15:59, after the reset.
- Interim results of the finished runs were looked at before `real-012` finished; the analysis was not changed.
