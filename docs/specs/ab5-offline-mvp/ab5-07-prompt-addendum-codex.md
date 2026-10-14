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
