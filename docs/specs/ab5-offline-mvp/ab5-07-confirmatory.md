# AB5-07 - confirmatory test on `real-001-bug` (pre-registered 2026-10-11, before any run)

Question: on `tasks/real-001-bug` (v2), does Codex gpt-6.1-sol on ChatGPT Plus pass more often than Claude Sonnet 5.5
on Claude Pro? The exploratory runs (10/28 vs 19/28 pooled; same-version groups p = 0.21 and p = 0.16) motivate the
question but are not evidence for it.

## Fixed in advance

- Manifest `experiments/real-001-bug-confirmatory.json`: 50 repetitions per config, seed 4242, balanced order.
- Configs: `claude-sonnet-pinned` (`claude -p --model claude-sonnet-5-5`, CLI `2.1.289 (Claude Code)`) and
  `codex-sol-pinned` (`codex exec -m gpt-6.1-sol`, CLI `codex-cli 0.160.0`). The runner refuses to start or resume
  when an installed CLI version differs from the pinned one; every trial's resolved model is recorded and must be
  `claude-sonnet-5-5` for Claude (Codex does not report one).
- Harness: the version pinned when the run starts (currently v0.8.4); one run directory, resumed only on quota stops.
- Grading: `patch-io` on the qualified target, one grading session per resume.
- Predeclared exclusion: outcome `error` (provider or quota errors before a result).
- Primary analysis, done once after all 100 trials are recorded: Fisher's exact two-sided test on PASS among
  non-excluded trials per config, alpha = 0.05. Secondary (reported, not decisive): the operational rate over all
  started trials and the Wilson intervals.
- Inconclusive, not extended, if either config has fewer than 45 non-excluded trials, if a resolved model differs,
  or if the CLI versions could not be held (a new pre-registration is needed then).
- Power (Monte Carlo, 1500 draws per point, alpha 0.05): 93% if the true rates are 0.36 vs 0.70; about 65-70% if they
  are 0.40-0.42 vs 0.65-0.68.

## Cost

Zero money (subscriptions, preflight enforced). About 100 trials: roughly 2 hours plus grading; it will span more than
one Claude Pro / ChatGPT Plus usage window, using `resume` after each quota stop.
