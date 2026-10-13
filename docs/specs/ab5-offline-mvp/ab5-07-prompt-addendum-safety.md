# AB5-07 - does the check-related instruction hurt where Claude already passes? (pre-registered 2026-10-13, before any run)

Question: the instruction from `ab5-07-prompt-addendum.md` raised Claude's PASS rate on the two discriminating tasks.
Does it lower PASS or slow Claude down on the nine symptom tasks where Claude passed every earlier trial
(`real-002-bug`, `real-003`, `real-005` v3, `real-006`, `real-007`, `real-008`, `real-009` v2, `real-010`, `real-011`)?
For example, it could change behaviour that was correct while looking for other inputs.

## Fixed in advance

- Manifests `experiments/prompt-addendum-safety-<task>.json`: the same two arms as the addendum experiment
  (`claude-sonnet-pinned` and `claude-sonnet-pinned-check-related`, same wording, pinned `claude-sonnet-5-5`, CLI
  `2.1.289 (Claude Code)`, harness v0.8.4), interleaved in one run per task, 3 repetitions per arm: 54 trials.
- Predeclared exclusion: outcome `error`. Resumes after quota stops allowed; interim looks disclosed.
- Primary analysis, once after all 54 trials: PASS pooled over the nine tasks, addendum arm vs same-run baseline,
  Fisher exact two-sided, alpha 0.05. The instruction is reported as harmful only if the addendum arm is lower and
  p < 0.05.
- Secondary, descriptive: every FAIL in either arm is examined and its cause described. For each task, the ratio of
  median PASS durations (addendum / baseline) is reported.
- Inconclusive if an arm has fewer than 24 non-excluded trials.
- Power (Monte Carlo, 2000 draws, baseline 0.98, n = 27 per arm): 13% if the addendum drops PASS to 0.85, 55% at 0.75,
  93% at 0.60. Only a large harm is likely to be detected. A small drop needs the FAIL examination or more trials.
