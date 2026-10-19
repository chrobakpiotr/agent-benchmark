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

## Result (runs 2026-10-19, harness v0.12.0)

| run | baseline PASS | with instruction | Fisher p | median PASS s baseline / instruction |
|---|---|---|---|---|
| Claude `real-016` | 4/19 (1 excluded, quota) | 5/20 | 1.0 | 81.8 / 91.9 |
| Codex `real-016` | 11/15 | 9/14 (1 excluded, provider error) | 0.70 | 76.0 / 92.5 |

**Primary analysis** (alpha 0.025 per run): the Claude run is not higher, and the Codex run is not lower. The verdict
is therefore **not "lifts Claude"**: on `real-016` the instruction did not help Claude, and no harm to Codex was
detected. Every arm has at least the required number of non-excluded trials.

**Secondary:**
- Without the instruction, 11 of 15 Claude FAILs read a missing count as 0. With it, 14 of 15 do, and every FAIL with
  the instruction fails all 6 bug cases.
- The instruction widened what Claude handled (absent, partial and empty cache objects) but gave each case the value
  ADR 0002 rules out.
- All 4 Codex baseline FAILs and 4 of 5 Codex FAILs with the instruction also read a missing count as 0.
- The instruction cuts in two directions:
  - On `real-012` and `real-001-bug` v3, Claude's gap was coverage, and the instruction closed it.
  - On `real-016` the gap is the documented value for unknown, and the instruction does not supply it. That matches
    what the instruction did for Codex on `real-001-bug` v2 (`ab5-07-prompt-addendum-codex.md`).

**Deviations:**
- Both runs started without sleep prevention. The host slept from about 10:30 to 15:43 CEST. A Codex trial running
  across the sleep ended as a provider error and is excluded as predeclared. The resumes ran under `caffeinate -i`.
- Claude stopped once on its usage limit and was resumed.
- Six trials were first left ungraded because a shared harness rehearsal held the host load at about 140-290. Each is
  in `warnings.log` with its load and job id. All were graded later by `resume`, as separate grade records.
- Harness paused its rehearsal (SIGSTOP) from about 07:55Z, and again from about 14:10Z after it had resumed.
- Interim counts were looked at during the run; the analysis was not changed.
