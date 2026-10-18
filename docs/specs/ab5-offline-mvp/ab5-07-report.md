# AB5-07 - pilot report (2026-10-10 to 2026-10-18)

Zero-spend live pilot comparing agent-CLI configurations on real bug-fix tasks. This report describes the current
state. Earlier versions, including the withdrawn reading of `real-001-bug` v2, are in git history. Sources:
- run records under `~/agent-benchmark-runs/` (events, evidence, grade records with B10 isolation evidence);
- task specs in `ab5-05a-real-task.md`;
- the pre-registered tests named below.

## Method

- **Configurations:**
  - `claude -p` (Claude Code 2.1.289, Sonnet 5.5) on Claude Pro;
  - `codex exec` (codex-cli 0.160.0, gpt-6.1-sol) on ChatGPT Plus;
  - OpenCode 1.19.0 with `nvidia/nemotron-3-super-120b-a12b:free` on a zero-limit OpenRouter key.

  Every run passed the zero-spend preflight; nothing was paid.
- **Execution:** agent-harness `AgentCliBackend` (v0.6.1-v0.8.4), controlled track. Each CLI runs in its own sandbox
  with a shell that has no network or DNS. The prompt goes in on stdin, and the candidate is the workspace diff, sealed
  by the harness.
- **Grading:** `patch-io` on the qualified Docker target. Only case inputs enter the container; the verdict is computed
  outside, from the answers file, against expected values that never enter it.
- **Tasks:** real fixes from agent-harness, pypa/packaging, python-semver, python-humanize, croniter and
  Python-Markdown. Each task has one reference patch per plausible reading and, from `real-009` on, a calibration trial
  before the full run. Most descriptions state symptoms only: one example, no general rule.
- **Statistics:** claims rest only on pre-registered tests (Fisher exact two-sided, Bonferroni where several tests
  share a question). Exclusions are predeclared (provider/quota `error`), and interim looks and resumes are disclosed.
  Everything else is descriptive.

## Results: agents without instructions

| task | description | Claude Sonnet (Pro) | Codex gpt-6.1-sol (Plus) | median trial s (C / X) |
|---|---|---|---|---|
| real-001 | spec | 5/5 | 5/5 | 21 / 44 |
| real-002 | spec | 4/4 | 4/4 | 14 / 49 |
| real-002-bug, 003, 005 v3, 006-011 (9 tasks) | symptom | 34/34 | 36/36 | 16-22 / 43-120 |
| **real-012** (`ab5-07-confirmatory-real-012.md`) | symptom; other forms of the same bug | **7/19** | **20/20** | ~30 / ~100 |
| **real-001-bug v3** (`ab5-07-confirmatory-real-001-bug-v3.md`) | symptom; rule in ADR 0002 | **7/20** | **20/20** | 33 / 68 |

- **Two confirmed discriminating tasks.** Each was decided by a pre-registered test: Fisher p = 1.3e-5 on both.
- **On both, Claude's fix diverges from the documented behaviour on inputs the report does not show:**
  - `real-012`: it misses other forms of the bug.
  - `real-001-bug` v3: it rejects a valid result, one whose authoritative summary overrides a stream event with a
    null unit.
  - Every Claude FAIL is in this class, and Codex passed every trial.
- **On the other 11 tasks both agents passed every valid trial.** These include rules from well-known specs
  (SemVer), Python's data model, and a convention stated in a code comment.
- **Claude was about 2-4x faster on every task.**
- **OpenCode + nemotron (free):** `real-001` 1/1; `real-001-bug` 0/2 under both v2 and v3 grading. A trial uses 20-40
  requests, so the free tier allows 1-2 trials per day.

## Results: one general instruction

Instruction v1 (config `prompt_addendum`, names no case): "The report shows one example. The same underlying problem
may show up with other inputs: before you finish, find them and make sure they are fixed too, without changing
behaviour that was correct."

| experiment | baseline | with instruction | p |
|---|---|---|---|
| Claude, `real-012` (`ab5-07-prompt-addendum.md`) | 2/19 | 16/20 | 1.7e-5 |
| Claude, 9 symptom tasks it already passed (`ab5-07-prompt-addendum-safety.md`) | 27/27 | 26/26 | 1.0; 1.47x slower |
| Claude, `real-001-bug` v3 (`ab5-07-prompt-addendum-v1-confirmed-tasks.md`) | 7/20 | 19/20 | 1.4e-4 |
| Codex, `real-001-bug` v3 / `real-012` (same document) | 15/15, 15/15 | 15/15, 14/14 | 1.0, 1.0; up to 1.7x slower |

- **Instruction v2 did not help both agents** (`ab5-07-prompt-addendum-docs.md`). v2 added "take the correct
  behaviour from the project's documentation and contracts". It gave Claude a smaller gain than v1 and, on the
  ambiguous v2 task, drove Codex to the reading the docs permit: 0/15.
- **Verdict on both confirmed tasks:** one general sentence that names no case lifts Claude to Codex's level
  (16/20 and 19/20), with no harm detected for Codex. The gap is mostly what Claude does by default, not what it
  can do.
- **What the instructions do.** They make an agent search more widely. They do not settle which reading of the newly
  found cases is right; that has to come from the task.

## `real-001-bug` v2 was ambiguous

The v2 hidden case `complete_without_summary` expected a stream-only result marked `complete` to be rejected. ADR
0002 says only that a summary, *if present*, is authoritative. "Without a summary, the streams are the usage" was
therefore a valid reading, and no reference patch covered it. Every v2 FAIL in every run was that case, so v2 results
measure a reading preference, not correctness. They include:
- the earlier confirmatory Claude 8/49 vs Codex 25/47;
- builder/reviewer;
- the instruction experiments on v2: Claude up with v1, Codex down from 16/20 to 3/20 with v1 and to 0/15 with v2.

The grades are kept as records of that choice and are not invalidated. v3 replaced the case with two cases the ADR
settles and added the second reading's reference patch (`ab5-05a-real-task.md`).

## What the pilot shows and does not show

- **The pipeline works end to end at zero cost:** subscription CLIs, sandboxed execution, harness-sealed candidates,
  qualified grading, correction records, offline re-grading against a new task version, and pre-registered analysis.
- **It shows a consistent difference on two of 13 tasks:** Claude handles inputs the report does not show less often
  than Codex. It does not rank the configurations in general.
- **Task design is the bottleneck.**
  - Six task versions were defective, among them `real-001-bug` v2, which was found only after many runs. The flaw
    showed when one agent, pointed at the docs, chose the other reading every time.
  - A useful check: when every FAIL is the same hidden case, look for a second reading of that case in the base's
    documentation before drawing conclusions.

## Threats to validity

- **Contamination:** all sources are public; fixes from 2026-06 to 2026-10 may still be known to the models.
- **Environment:** one machine and one time window. Durations depend on provider load.
- **Post-hoc design:** v3 was designed after the v2 runs. Its first numbers came from a re-grade, and the claim rests
  only on the later pre-registered run.
- **Interim looks and resumes** are disclosed in each test document; no decision depended on them.
