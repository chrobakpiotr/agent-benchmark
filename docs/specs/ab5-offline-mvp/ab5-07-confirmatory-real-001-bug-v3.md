# AB5-07 - confirmatory test on `real-001-bug` v3 (pre-registered 2026-10-17, before any v3 run)

Hypothesis (from the post-hoc re-grade of the v2 candidates, `ab5-05a-real-task.md`): on v3, Codex passes more often
than Claude. The expected mechanism is that Claude rejects a valid result whose summary overrides a stream event with
a null unit (`complete_summary_overrides_null_stream`). Re-grade rates were Codex 144/144 and Claude 37/112. They come
from v2 trials and a case added afterwards, so they motivate this test but do not count as evidence for it.

## Fixed in advance

- Calibration first: `experiments/real-001-bug-v3-calibration.json`, 1 trial per config. It checks only that trials
  complete and are graded on the qualified target. It does not count, and no result from it changes this plan.
- Confirmatory run: `experiments/real-001-bug-v3-confirmatory.json`, 20 repetitions per config, interleaved. Pinned
  `claude-sonnet-5-5` / CLI `2.1.289 (Claude Code)` and `gpt-6.1-sol` / `codex-cli 0.160.0`, no prompt addendum,
  harness v0.8.4.
- Predeclared exclusion: outcome `error`. Resumes after quota stops are allowed; interim looks are disclosed.
- Primary analysis, once after all 40 trials: Fisher exact two-sided test, Codex vs Claude PASS, alpha 0.05.
- Secondary, descriptive: FAILs by hidden case, and the share of Claude FAILs on the override case.
- Inconclusive if a config has fewer than 18 non-excluded trials.
- Power (Monte Carlo, 2000 draws, n = 20 per config, alpha 0.05, Codex 0.95): 99% for Claude 0.33, 89% for 0.50, 70%
  for 0.60.
