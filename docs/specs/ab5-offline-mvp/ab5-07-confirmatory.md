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

## Result (run 2026-10-12, `~/agent-benchmark-runs/real-001-bug-confirmatory-2026-10-12`)

| config | PASS / non-excluded | Wilson 95% | excluded (outcome `error`) | operational |
|---|---|---|---|---|
| `claude-sonnet-pinned` | 8/49 (16.3%) | [0.085, 0.290] | 1 (Claude Pro quota) | 8/50 |
| `codex-sol-pinned` | 25/47 (53.2%) | [0.392, 0.667] | 3 (OpenAI "model at capacity" x2, 503 x1) | 25/50 |

- Primary analysis (Fisher's exact, two-sided, non-excluded trials): **p = 0.0002**, a significant difference at
  alpha = 0.05. Secondary: operational 8/50 vs 25/50, p = 0.0006; the Wilson intervals do not overlap, so the
  conservative `compare` rule also declares a difference.
- Validity conditions held: 49 and 47 non-excluded trials (>= 45); every Claude trial resolved to `claude-sonnet-5-5`;
  CLI versions `2.1.289 (Claude Code)` / `codex-cli 0.160.0` for the whole run (resume refuses a change); one harness
  version (v0.8.4).
- All 63 failures are the same case, `complete_without_summary` (the rule the report does not state).
- Deviations, disclosed: (1) the owner asked for interim PASS percentages during the run; they were shown but no
  decision depended on them and the run was not stopped early; (2) the plan named quota stops as the reason to
  resume; the run was also resumed after OpenAI capacity errors, twice with a delay (20 and 45 minutes); four resumes
  in total.
- Conclusion: on `real-001-bug` (v2), with these pinned versions, Codex gpt-6.1-sol on ChatGPT Plus infers the unstated
  rule more often than Claude Sonnet 5.5 on Claude Pro. This is one task; it says nothing about other tasks, where both
  passed every valid trial.

## Correction (2026-10-17)

The `complete_without_summary` case has a second plausible reading that no reference patch covers. Its input has `usage_completeness: "complete"` and one `stream` event with integer units and no `summary`. ADR 0002 in the base says only that a summary, *if present*, is authoritative and that stream events are informational. Neither the base code nor its docs say that `complete` requires a summary. "Without a summary, the stream events are the usage" is therefore consistent with the docs, and patches that read it that way fail this case. Every real-001-bug FAIL in every run fails exactly this case. The result above therefore shows how often each arm chose the reading the task's hidden case expects (the
upstream fix's reading). It does not show correctness. See `ab5-05a-real-task.md`.
