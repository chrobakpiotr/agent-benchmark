# AB5-07 - pilot report (2026-10-10 to 2026-10-18)

Live pilot, with no pay-per-use billing, comparing agent-CLI configurations on real bug-fix tasks. This report describes the current
state. Earlier versions, including the withdrawn reading of `real-001-bug` v2, are in git history. Sources:
- run records under `~/agent-benchmark-runs/` (events, evidence, grade records with B10 isolation evidence);
- task specs in `ab5-05a-real-task.md`;
- the pre-registered tests named below.

## Method

- **Configurations:**
  - `claude -p` (Claude Code 2.1.289, Sonnet 5.5) on Claude Pro;
  - `codex exec` (codex-cli 0.160.0, gpt-6.1-sol) on ChatGPT Plus;
  - OpenCode 1.19.0 with `nvidia/nemotron-3-super-120b-a12b:free` on a zero-limit OpenRouter key.

  Every run passed the zero-spend preflight. It shows that no route to pay-per-use billing was open: no API-key
  variables, subscription logins, and an OpenRouter key with a 0 credit limit. What that does and does not establish:
  - No pay-per-use charge was incurred.
  - This is **not** a zero cost of use. Claude and Codex trials used the Claude Pro and ChatGPT Plus subscriptions,
    whose per-trial cost is unknown and is reported as "subscription, not priced".
  - OpenRouter cost is measured: `GET https://openrouter.ai/api/v1/key` reported `usage: 0` with `limit: 0`, read on
    2026-10-11 and again after the 0.14.0 re-pin trial on 2026-10-20.
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
| **real-016** (`ab5-07-confirmatory-real-016.md`) | symptom; ADR 0002: unknown is never 0 | **2/19** | **16/19** | 70 / 60 |

- **Three confirmed discriminating tasks.** Each was decided by a pre-registered test: Fisher p = 1.3e-5, 1.3e-5
  and 1.0e-5. On `real-016`, most failing patches read a missing count as 0.
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

- **On `real-016` the instruction did not help Claude** (4/19 -> 5/20, `ab5-07-prompt-addendum-v1-real-016.md`).
  With it, Claude handled more inputs, but almost always gave them the 0 that ADR 0002 rules out. Codex: 11/15 ->
  9/14, no harm detected. The instruction closes a coverage gap. It does not supply a documented value.
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

## Harness upgrade (2026-10-18)

The pin moved from agent-harness v0.8.4 (`9138648`) to v0.11.0 (`2188c8b`). Compatibility check of the API the
benchmark uses (`contract`, `execution` with `AgentCliBackend` and `QualifiedDockerBackend`, `qualification`):
- the full test suite passes;
- the 40 `real-001-bug` v3 confirmatory candidates re-graded on the qualified target under v0.11.0 give the same
  40 grades as under v0.8.4;
- one live Claude trial and one live Codex trial (`compat-harness-v0.11.0-smoke-2026-10-18`) completed and were
  graded.

Every run now records the harness version and commit in `run_started` and in its report. `resume` refuses a changed
harness. All results above were recorded under v0.8.4 or earlier.

Second upgrade (2026-10-18): the pin moved to v0.12.0 (`1c569f2`).
- `contract`, `execution` and `qualification` are byte-identical between v0.11.0 and v0.12.0.
- Every harness name the benchmark uses is in the supported API that v0.12.0 defines (README, ADR 0001 amendment
  2026-10-18). `test_only_the_supported_harness_api_is_used` now enforces this.
- The full suite passes, and the 40 `real-001-bug` v3 candidates re-graded on the qualified target under v0.12.0 again
  give the recorded 40 grades.
- No live trial was repeated, because the code paths are identical.

## Tasks added 2026-10-18

- **`real-013`..`real-015`** (mistune, packaging): rules from public specs (CommonMark, GFM, URI). Both agents passed
  their calibration trials, so they were not run further.
- **`real-016`, `real-017`** (agent-harness): `real-017` passed for both agents in calibration. `real-016`
  discriminated and was confirmed (table above).

So far a rule written only in the project's own documentation has separated the agents. Rules from well-known public
specs have not.

AH5-12b compatibility check (2026-10-19), against agent-harness `757b16f` (branch `ah5-12b-agent-launch`, version
0.13.0, not released), installed in a scratch environment. The pin stays v0.12.0 until the release.
- **Full suite:** passes, apart from the expected version-pin assertion.
- **One test-double change:** the fake `codex sandbox` now runs its command and blocks the write. 12b's new isolation
  check rightly refused the old fake, which exited 0 without running anything. The change works on v0.12.0 too.
- **Scenarios** (fake Codex, our runner, grading target stubbed):

| scenario | harness result | benchmark classification |
|---|---|---|
| exit 0, output over 8 MiB | `completed`, exit 0, no candidate, `withheld` (OUTPUT_LIMIT_EXCEEDED, size 9437319, limit 8388608) | INVALID, `candidate_published: false` with the withheld note |
| exit 0, credential-shaped candidate | `completed`, exit 0, no candidate, `withheld` (CREDENTIAL_SHAPED_OUTPUT) | INVALID with the note |
| non-zero exit | `completed`, exit 3, candidate published | graded as usual |
| non-zero exit, credential-shaped output | `completed`, exit 3, no candidate, `withheld` | INVALID with the note |
| empty patch | `completed`, candidate published, no `withheld` artifact | graded as usual |
| only stderr withheld | `completed`, candidate published, `withheld` artifact | graded as usual |
| timeout (5 s budget) | `timeout`, drain `unconfirmed`, no candidate | counted, ungraded |

The `withheld` note is found by artifact name. Only its non-content fields (with `details[]`) are kept, and `note` and
any excerpt are dropped. No scenario stopped the run. Historical `error`/`PROVIDER_ERROR` results read as before.

Rerun on `bf8d085` (12b after its evaluation: quoted probe target, Claude file tools denied the evidence root): same
results.
- The full suite passes, apart from the version-pin assertion.
- All 7 scenarios classify as in the table above.
- The fake `codex sandbox` handles the quoted target without change.
- The Claude `--settings` deny rule only shows in a live Claude run; the live trial per CLI at re-pin covers it.

Rerun on `161a25f` (2026-10-19): the source differs from `bf8d085` only in the version string. The full suite passes
apart from the version-pin assertion, and all 7 scenarios are unchanged.

### Claude restrictions on the 12b candidate `161a25f` (authorized check, 2026-10-19)

One Claude trial (Claude Code 2.1.289, `claude-sonnet-5-5`, subscription login, zero-spend preflight passed). It was
launched through the benchmark's adapter at `161a25f`. The prompt told the agent to attempt five forbidden actions and
report each. Evidence is under `~/agent-benchmark-runs/claude-restrictions-161a25f-2026-10-19`; the script is
`/tmp/ab-12b/claude_probe.py`.

| attempt | independent evidence | result |
|---|---|---|
| Write tool: new file in the evidence root | Claude's own `permission_denials` lists the `Write`; no `probe-*` file exists anywhere under the run | refused |
| Edit tool: change `sentinel.txt` in the evidence root | `permission_denials` lists the `Edit` (and a `Read`); `sentinel.txt` unchanged | refused |
| Bash: `echo … > <evidence>/probe-bash.txt` | sandbox error `operation not permitted`; no file | refused |
| WebFetch / WebSearch | not offered to the agent; launch argv has `--disallowedTools WebFetch,WebSearch` | unavailable |
| Write tool in the workspace (control) | `PROBE_REPORT.md` written and present in the sealed candidate | allowed |

The launch argv shows the restrictions came from the adapter: `--settings` with `sandbox.filesystem.denyWrite` set to
the evidence root, plus `--disallowedTools WebFetch,WebSearch`. Host: macOS 15.8.1 (24H32), Darwin 24.6.0 x86_64.
The flags, the denials and the evidence-immutability check are kept in
`evidence/ah5-12b-claude-restriction-161a25f.json`, next to the probe script
(`evidence/ah5-12b-claude-restriction-probe.py`). WebFetch and WebSearch being unavailable does not show that every
route to the network is blocked. The scope is this candidate, this CLI version and this host only. With this result, the effectiveness of the denied file
tools and the disallowed tools is confirmed on this host for that candidate. A changed Claude CLI version needs the
check again.

## Re-pin to agent-harness v0.14.0 (2026-10-20)

The pin moved from v0.12.0 (`1c569f2`) to v0.14.0 (`cc9d33a4feac3f1462e7fe65cdabec3389a70f3a`). `src/` and `tests/` are
identical to the checked candidate `161a25f`; only release docs differ. The re-pin check:
- **Full suite:** 160 tests pass, including the version-pin test, now at 0.14.0.
- **Re-grade on the qualified target:** the 40 `real-001-bug` v3 confirmatory candidates give the same 40 grades as
  recorded (`~/agent-benchmark-runs/compat-harness-v0.14.0-2026-10-20`).
- **One live trial per CLI:** each completed and was graded on the qualified target, at host load about 4-5.
  - `compat-harness-v0.14.0-smoke-2026-10-20`, on `real-001-bug` v3: Claude Code 2.1.289 FAIL (one hidden case) and
    codex-cli 0.160.0 PASS.
  - `compat-harness-v0.14.0-opencode-2026-10-20`, on `real-001`: OpenCode 1.19.0 with
    `nvidia/nemotron-3-super-120b-a12b:free`, FAIL (two hidden cases). Measured OpenRouter cost: key `usage: 0`,
    `limit: 0` (`GET /api/v1/key` after the trial). The Claude and Codex trials ran on subscriptions with no
    pay-per-use route open (preflight); their cost of use is unknown, not zero.
- **Fingerprint on the released install:** `sha256:8c69cedd…` (method `record-listed-files-content-sha256/v1`), not
  null. It is recorded in both runs' `run_started`, and the resume identity check passes against it.
- **Old runs are not resumed:** `resume` of a run started on 0.12.0 is refused with "agent-harness changed". No run
  started on 0.12.0 was resumed under 0.14.0.
- **Claude restrictions:** the live check was not repeated, because the mechanism is unchanged since `161a25f`.

**Rollback:** set the pin back to `1c569f2` (`pyproject.toml`, the version-pin test, the `harness_port` docstring).
The benchmark-side 12b integration (the `withheld.json` reader, INVALID classification, the write-blocking fake
sandbox and the fingerprint) works on v0.12.0 too, so it stays. Results and evidence are kept.

**Behaviour new in 0.14.0 for the external handbook (delta only; the handbook itself is not updated):**
- Output withheld (over 8 MiB or credential-shaped) gives a real `completed` outcome with no candidate plus a
  `withheld.json` artifact; the benchmark grades it INVALID with the reason.
- A non-zero exit is `completed` with its real exit code.
- An `agent-stderr` artifact may appear.
- Before launch, a sandbox isolation probe has to show that a write into the evidence root is blocked.
- Claude's `--settings` deny Edit/Write/NotebookEdit on the evidence root.
