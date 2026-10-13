# AB5-07 - final pilot report (2026-10-10 to 2026-10-13)

Zero-spend live pilot comparing agent-CLI configurations on real bug-fix tasks. Sources: the run records under
`~/agent-benchmark-runs/` (events, evidence, grade records with B10 isolation evidence); task specs in
`ab5-05a-real-task.md`; the pre-registered test in `ab5-07-confirmatory.md`.

## Method

- Configurations: `claude -p` (Claude Code 2.1.289, Sonnet 5.5) on Claude Pro; `codex exec` (codex-cli 0.160.0,
  gpt-6.1-sol) on ChatGPT Plus; OpenCode 1.19.0 with `nvidia/nemotron-3-super-120b-a12b:free` on a zero-limit
  OpenRouter key. Every run passed the zero-spend preflight; nothing was paid.
- Execution: agent-harness `AgentCliBackend` (v0.6.1-v0.8.4), controlled track: each CLI in its own sandbox,
  shell without network or DNS, prompt on stdin, candidate = workspace diff sealed by the harness.
- Grading: `patch-io` on the qualified Docker target (one qualification session per run): only case inputs enter
  the container; the verdict is computed outside from the answers file against expected values that never enter it.
- Tasks: 12 valid real tasks from agent-harness, pypa/packaging, python-semver, python-humanize and croniter, each
  with reference patches for every plausible reading and (from real-009 on) a calibration trial before the full run.
- Records: 305 agent trials in total; 266 graded; 27 invalidated through correction records (task defects,
  quota artefacts); 10 ended in provider or quota errors (never graded).

## Results (valid grades only)

| task | description | Claude Sonnet (Pro) | Codex gpt-6.1-sol (Plus) | median trial s (C / X) |
|---|---|---|---|---|
| real-001 | spec | 5/5 | 5/5 | 21 / 44 |
| real-002 | spec | 4/4 | 4/4 | 14 / 49 |
| real-002-bug | symptom | 4/4 | 4/4 | 20 / 56 |
| real-003 | symptom | 2/2 | 4/4 | 20 / 66 |
| real-005 v3 | symptom | 4/4 | 4/4 | 19 / 50 |
| real-006 | symptom | 4/4 | 4/4 | 17 / 43 |
| real-007 | symptom | 4/4 | 4/4 | 20 / 49 |
| real-008 | symptom | 4/4 | 4/4 | 21 / 61 |
| real-009 v2 | symptom | 4/4 | 4/4 | 22 / 65 |
| real-010 | symptom | 4/4 | 4/4 | 16 / 120 |
| real-011 | symptom | 4/4 | 4/4 | 20 / 76 |
| **real-001-bug v2, confirmatory** | symptom, rule only in the contract's meaning | **8/49** | **25/47** | 22 / 120 |

- The only discriminating task was decided by the pre-registered test: Fisher exact two-sided p = 0.0002, Wilson
  intervals [0.09, 0.29] vs [0.39, 0.67]. Every failure is the same unstated rule.
- On the other 11 tasks both configurations passed every valid trial, including rules taken from well-known specs
  (SemVer), Python's data model and a project convention stated in a code comment.
- Claude was 2.5-4x faster on every task (Codex 43-120 s, Claude 14-22 s per trial).
- Builder/reviewer on real-001-bug: Codex builds + Claude reviews 3/4; Claude builds + Codex reviews 0/3. A reviewer
  given the same report did not add the unstated rule.
- OpenCode + nemotron (free): real-001 1/1; real-001-bug 0/2 graded, failing the same rule and also rejecting a valid
  result; 20-40 requests per trial, so 1-2 trials per day on the free tier.

## What the pilot shows and does not show

- It shows that the pipeline works end to end at zero cost: subscription CLIs, sandboxed execution, harness-sealed
  candidates, qualified grading, correction records, pooled and pre-registered analysis.
- It shows one established difference between two configurations on one task. It does not rank the configurations
  in general: 11 of 12 tasks did not discriminate.
- Task design is the bottleneck. Five task versions were defective (ambiguous descriptions, a missing `.gitignore`,
  library conventions that admit two readings); calibration trials and one reference patch per plausible reading now
  catch most of this before a full run. Discriminating tasks need a rule that is not visible in or near the code.

## Threats to validity

- Contamination: all sources are public; fixes from 2026-06 to 2026-10 may still be known to the models.
- One machine, one time window; durations depend on provider load (Codex saw capacity errors).
- Exploratory pools mixed harness versions (harness confirmed identical agent inputs); the confirmatory run used one
  pinned version of every component.
- Interim looks during the confirmatory run were disclosed; no decision depended on them.

## Next

Find more tasks whose correct behaviour is defined only in project documentation (ADRs, format specs), measure cost
and time on the existing set, and continue the free third configuration at its daily pace.
