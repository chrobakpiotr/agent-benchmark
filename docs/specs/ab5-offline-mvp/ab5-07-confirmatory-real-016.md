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

## Result (run 2026-10-18/19, `~/agent-benchmark-runs/real-016-confirmatory-2026-10-18`, harness v0.12.0)

| config | PASS / non-excluded | excluded | Wilson 95% | median PASS s |
|---|---|---|---|---|
| `claude-sonnet-pinned` | 2/19 | 1 (quota) | [0.029, 0.314] | 69.9 |
| `codex-sol-pinned` | 16/19 | 1 (provider error) | [0.624, 0.945] | 60.3 |

**Primary analysis:** Fisher exact two-sided p = 1.0e-5 < 0.05. On `real-016` Codex passes more often than Claude.
Both configs have 19 non-excluded trials.

**Secondary:**
- 12 of 17 Claude FAILs fail all 6 bug cases. The other 5 fail only the partial or empty cache-object cases.
- 11 Claude FAILs and all 3 Codex FAILs add a 0 default for a missing count (e.g. `get("read", 0)`), the reading
  ADR 0002 rules out.

**Deviations:**
- The run stopped on Claude's usage limit after 11 trials and on a Codex provider error after 30. It was resumed both
  times.
- Interim PASS counts were looked at (0/5 vs 4/5, then 2/14 vs 12/14); the analysis was not changed.

**Conclusion:** `real-016` is a third confirmed discriminating task, after `real-012` and `real-001-bug` v3. All three
rest on a rule documented in the project, not stated in the report. Two of them (`real-001-bug` v3 and `real-016`)
use the same ADR rule: unknown is never 0.
