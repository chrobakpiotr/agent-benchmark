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

## Result (run 2026-10-13, `~/agent-benchmark-runs/real-012-confirmatory-2026-10-13`)

| config | PASS / non-excluded | Wilson 95% | excluded | operational |
|---|---|---|---|---|
| `claude-sonnet-pinned` | 7/19 (36.8%) | [0.19, 0.59] | 1 (Claude Pro quota) | 7/20 |
| `codex-sol-pinned` | 20/20 (100%) | [0.84, 1.00] | 0 | 20/20 |

- Primary analysis (Fisher exact, two-sided): **p = 1.3e-5**; Wilson intervals separated. Validity conditions held
  (19 and 20 non-excluded trials, >= 18; Claude resolved to `claude-sonnet-5-5` throughout; pinned CLI versions; one
  harness version; one resume after the quota stop, as allowed).
- All 12 Claude failures are the same two cases: an unterminated end tag with a later `>` and one with a trailing
  slash still drop the rest of the document (the reported data loss).
- Disclosed deviation: the owner asked for interim status six times; no decision depended on it.
- Conclusion: on `real-012`, with these pinned versions, Codex gpt-6.1-sol covers the unstated variants of the reported
  bug more reliably than Claude Sonnet 5.5. Second task, same direction as `real-001-bug`.
