# AB5-07 - does one general instruction close Claude's gap? (pre-registered 2026-10-13, before any run)

Question: on the two discriminating tasks (`real-001-bug` v2, `real-012`), where Claude missed unstated parts of the
reported bug (confirmatory: 8/49 and 7/19 vs Codex 25/47 and 20/20), does adding one general instruction to Claude's
prompt raise its PASS rate?

## Fixed in advance

- Instruction (config `prompt_addendum`, identical for both tasks, names no case): "The report shows one example. The same underlying problem may show up with other inputs: before you finish, find them and make sure they are fixed too, without changing behaviour that was correct."
- Manifests `experiments/prompt-addendum-real-001-bug.json` and `experiments/prompt-addendum-real-012.json`: two Claude
  arms interleaved in one run per task - `claude-sonnet-pinned` (no addendum, same-run baseline) and
  `claude-sonnet-pinned-check-related` (addendum) - 20 repetitions per arm; pinned `claude-sonnet-5-5`, CLI
  `2.1.289 (Claude Code)`, harness v0.8.4.
- Predeclared exclusion: outcome `error`. Resumes after quota/capacity stops allowed; interim looks disclosed.
- Primary analysis, once per task after all its 40 trials: Fisher exact two-sided, addendum arm vs same-run baseline,
  alpha 0.025 per task (Bonferroni over the two tasks). Secondary, descriptive only: the addendum arm against Codex's
  confirmatory rate (different run).
- Inconclusive if an arm has fewer than 18 non-excluded trials.
- Power (Monte Carlo, 2000 draws, n = 20 per arm, alpha 0.025): 44% for 0.16 -> 0.50, 68% for 0.16 -> 0.60, 89% for
  0.37 -> 0.90, 49% for 0.37 -> 0.75. Only a large effect is likely to be detected; a non-significant result is not
  evidence that the instruction does nothing.
