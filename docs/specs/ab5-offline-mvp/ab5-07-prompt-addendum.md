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

## Result: `real-012` (run 2026-10-13, 40 trials)

| arm | PASS / non-excluded | excluded | Wilson 95% |
|---|---|---|---|
| `claude-sonnet-pinned` (baseline) | 2/19 | 1 (`PROVIDER_ERROR`, usage limit, r20) | [0.029, 0.314] |
| `claude-sonnet-pinned-check-related` (addendum) | 16/20 | 0 | [0.584, 0.919] |

Primary analysis: Fisher exact two-sided p = 1.7e-5 < 0.025, so the instruction raised Claude's PASS rate on this task.
Both arms have at least 18 non-excluded trials. Secondary (descriptive, different run): Codex's confirmatory rate
was 20/20. The addendum arm's median PASS time was 37.8 s, against 30.4 s for the baseline.
Deviations: the run stopped on the usage limit at its last trial and was not resumed. Interim PASS counts were
looked at during the run; the analysis and threshold were not changed.

## Result: `real-001-bug` (run 2026-10-13, 40 trials)

| arm | PASS / non-excluded | excluded | Wilson 95% |
|---|---|---|---|
| `claude-sonnet-pinned` (baseline) | 3/20 | 0 | [0.052, 0.360] |
| `claude-sonnet-pinned-check-related` (addendum) | 16/19 | 1 (`PROVIDER_ERROR`, usage limit, r1) | [0.624, 0.945] |

Primary analysis: Fisher exact two-sided p = 1.9e-5 < 0.025, so the instruction raised Claude's PASS rate on this task
as well. Both arms have at least 18 non-excluded trials. Secondary (descriptive, different run): Codex's confirmatory
rate was 25/47. Median PASS time was 31.0 s with the addendum and 29.8 s without it.
Deviations: the run stopped on the usage limit after its first trial and was resumed once after the reset. Interim
PASS counts were looked at during the run; the analysis and threshold were not changed.

## Conclusion

On both discriminating tasks, one general instruction that names no case moved Claude from about 15% to about 80%
PASS. That is in line with Codex on `real-012` (20/20) and above Codex's earlier rate on `real-001-bug` (25/47); those
comparisons come from different runs and are descriptive only. Most of Claude's gap on these tasks is therefore
explained by how far it looks for other inputs with the same problem when not asked, rather than by whether it can fix
them. Limits: two tasks, one model and one wording; it is not known whether the instruction changes behaviour on
tasks where the report is already complete. Codex was not run with the addendum.
