# AB5-07 - confirmatory test on `real-016` (pre-registered 2026-10-18, before the confirmatory run)

Hypothesis: on `real-016` Codex passes more often than Claude. The rule is in ADR 0002 of the base: a missing count
is unknown, never 0. In calibration (1 trial per agent, not counted) Claude read a missing cache count as 0 and failed
all 6 bug cases, and Codex passed.

## Fixed in advance

- `experiments/real-016-confirmatory.json`: 20 repetitions per config, interleaved. Pinned `claude-sonnet-5-5` / CLI
  `2.1.289 (Claude Code)` and `gpt-6.1-sol` / `codex-cli 0.160.0`, no prompt addendum, harness v0.12.0 (recorded in
  `run_started`).
- Predeclared exclusion: outcome `error`. Resumes after quota stops are allowed.
- Trials left ungraded because the grading target did not qualify are graded by `resume`. They are never counted as
  FAIL.
- Interim looks are disclosed.
- Primary analysis, once after all 40 trials: Fisher exact two-sided test, Codex vs Claude PASS, alpha 0.05.
- Secondary, descriptive: FAILs by hidden case, and the share of Claude FAILs that read a missing count as 0.
- Inconclusive if a config has fewer than 18 non-excluded trials.
- Power (Monte Carlo, 2000 draws, n = 20 per config, alpha 0.05, Codex 0.95): >99% for Claude 0.30, 89% for 0.50,
  70% for 0.60.
