# AB5-07 - the check-related instruction on `real-016` (pre-registered 2026-10-19, before any run)

Question: does the v1 check-related instruction lift Claude on `real-016`, a task built after the instruction was
designed, and does it leave Codex unharmed? On the two earlier confirmed tasks it lifted Claude to Codex's level
(`ab5-07-prompt-addendum.md`, `ab5-07-prompt-addendum-v1-confirmed-tasks.md`). Confirmatory baseline on `real-016`:
Claude 2/19 and Codex 16/19. Most failing patches read a missing count as 0, which ADR 0002 rules out.

The instruction asks the agent to find other inputs with the same problem "without changing behaviour that was
correct". It does not mention documentation or unknown values. A gain therefore depends on Claude finding the ADR rule
itself.

## Fixed in advance

- Instruction: v1, worded exactly as before.
- Two runs, each with two interleaved arms: the pinned config without an addendum (same-run baseline) and
  `<config>-check-related`.
  - `experiments/prompt-addendum-v1-claude-real-016.json`: 20 repetitions per arm.
  - `experiments/prompt-addendum-v1-codex-real-016.json`: 15 repetitions per arm.
- Pinned `claude-sonnet-5-5` / CLI `2.1.289 (Claude Code)` and `gpt-6.1-sol` / `codex-cli 0.160.0`. Harness v0.12.0,
  recorded per run.
- Predeclared exclusion: outcome `error`. Resumes after quota or provider stops are allowed.
- Ungraded trials are graded by `resume`, never counted as FAIL. Interim looks are disclosed.
- The host load at grading time is recorded in each grade.
- Primary analysis, once per run after all its trials: Fisher exact two-sided test, addendum arm vs same-run
  baseline, alpha 0.025 per run (Bonferroni over two).
- Verdict "lifts Claude without harming Codex" only if both hold: the Claude run is significantly higher, and the
  Codex run is not significantly lower. Otherwise report each run as found.
- Inconclusive for a run if an arm has fewer than 18 (Claude) or 13 (Codex) non-excluded trials.
- Secondary, descriptive:
  - FAILs by hidden case;
  - the share of FAILs that read a missing count as 0;
  - median PASS duration ratio.
- Power (Monte Carlo, 2000 draws, alpha 0.025):
  - Claude, n = 20: 99% for 0.10 -> 0.80, 64% for 0.10 -> 0.50.
  - Codex, n = 15: a drop is detected with 52% probability for 0.85 -> 0.40 and 13% for 0.85 -> 0.60.
