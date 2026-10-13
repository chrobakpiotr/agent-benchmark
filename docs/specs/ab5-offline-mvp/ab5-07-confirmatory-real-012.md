# AB5-07 - confirmatory test on `real-012` (pre-registered 2026-10-13, before any confirmatory run)

Question: on `tasks/real-012` (Python-Markdown `7c265bc`, v1), does Codex gpt-6.1-sol on ChatGPT Plus pass more
often than Claude Sonnet 5.5 on Claude Pro? Motivating, exploratory data (not evidence): calibration 0/1 vs 1/1 and
the full run 0/4 vs 4/4; every Claude failure leaves the reported data loss in place for an end tag with a later `>`
and for one with a trailing slash.

## Fixed in advance

- Manifest `experiments/real-012-confirmatory.json`: 20 repetitions per config, seed 1212, balanced order.
- Same pinned configs as `ab5-07-confirmatory.md`: `claude-sonnet-pinned` (`claude-sonnet-5-5`, CLI `2.1.289
  (Claude Code)`) and `codex-sol-pinned` (`gpt-6.1-sol`, CLI `codex-cli 0.160.0`); the runner refuses a different
  installed CLI; harness v0.8.4.
- Predeclared exclusion: outcome `error` (provider, capacity or quota errors before a result).
- Primary analysis, once after all 40 trials: Fisher's exact two-sided test on PASS among non-excluded trials, alpha
  0.05. Secondary: operational rate over started trials, Wilson intervals.
- Inconclusive, not extended, if either config has fewer than 18 non-excluded trials or a pinned version could not be
  held. Resumes after quota or capacity stops are allowed; interim looks, if any, are disclosed.
- Power (Monte Carlo, 2000 draws): about 100% if the true rates are 0.10 vs 0.90; 85% if 0.30 vs 0.80.
