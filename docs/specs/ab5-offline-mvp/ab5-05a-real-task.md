# AB5-05a - real task `real-001`

Status: draft. Track: **transparent diagnostic** (host grading of authored reference patches only; untrusted
candidates need the qualified target of AB5-05b). Grader: `patch-io` v1.

## Choice

Real fix from a public repository, gradable inside the AB5-05b boundary (stdlib Python, no network, small):
agent-harness commit `2ada5ff` "fix(contract): require integer units for complete usage" (2026-10-05, MIT).
Showcase tasks were not used: Java/Gradle needs dependency downloads and more memory than B5/B8 allow; S30-06 is
excluded by the plan. Contamination: the repository is public, so a model with browsing or later training data may
have seen the fix; this is recorded in `task.json` `provenance`.

## Bundle `tasks/real-001`

`base/` = agent-harness at `af994d7` (parent of the fix) without `.github`, incl. `LICENSE`. Scope:
`src/agent_harness/contract.py`, `src/agent_harness/contract_fixtures/success.json` (the files the real fix
changed under `src/`); tests are out of scope. Visible check: `PYTHONPATH=src python -m unittest
tests.test_contract tests.test_boundaries` (the packaging tests need an installed package and are not task checks).
Hidden: 6 `validate_result` calls (`hidden/cases.json`, inputs only) with expected value or `ContractError`
(`expected/expected.json`): integer units under `complete` valid; null cache/input units under `complete` rejected;
missing summary under `complete` rejected; null units under `partial` valid; `unknown` without events valid.
Reference patches: `good` (the real src diff), `noop`, `wrong` (checks null units only), `overstrict` (rejects
null units under every completeness), `test_deletion`.

## AC -> evidence (`tests/test_real_task.py`)

| AC | Test |
|---|---|
| base fails, real fix passes | `test_real_fix_passes`, `test_base_and_partial_or_overstrict_fixes_fail_on_behaviour` (noop) |
| partial / over-strict fixes fail on behaviour | `test_base_and_partial_or_overstrict_fixes_fail_on_behaviour` |
| test manipulation | `test_test_deletion_is_out_of_scope` |
| bundle pinned and complete | `test_bundle_matches_pinned_digests`, `test_visible_checks_pass_on_base` |
| end to end through the fake runner | `test_fake_run_grades_reference_patches` |

# Real task `real-002`

Harder than `real-001`: two independent gaps in agent-harness contract v2, one of them an equality-versus-type trap.
Source: agent-harness commit `b29dfdf` "fix(contract): exact applied limits, explicit limits for qualified requests,
backend targets" (2026-10-07, MIT); base = parent `f2eeda2` (without `.github`). Scope:
`src/agent_harness/contract.py` (the commit's `execution.py` change is out of scope). Visible check:
`PYTHONPATH=src python -m unittest tests.test_contract tests.test_contract_v2 tests.test_boundaries`.

Hidden: 9 cases. `validate_request`: qualified without limits rejected; qualified with limits and plain without
limits valid. `validate_result`: exact applied valid; `True` for a limit of 1, a float limit, a float timeout, an
extra key and a different value rejected. The base fails 4 of them. Reference patches: `good` (real fix), `noop`,
`request_only`, `applied_only` (each half), `overstrict` (limits required on every v2 request), `test_deletion`.

| AC | Test (`tests/test_real_task.py`, `RealTask2`) |
|---|---|
| base fails, real fix passes | `test_real_fix_passes`, `test_base_half_and_overstrict_fixes_fail_on_behaviour` |
| each half fix and an over-strict fix fail on behaviour | `test_base_half_and_overstrict_fixes_fail_on_behaviour` |
| test manipulation | `test_test_deletion_is_out_of_scope` |
| bundle pinned and complete | `test_bundle_matches_pinned_digests`, `test_visible_checks_pass_on_base` |
| end to end through the fake runner | `test_fake_run_grades_reference_patches` |

Agent run: `experiments/real-002.json` (same configs as the AB5-07 pilot, 4 repetitions each).

# Bug-report variants (`task-bug-report.json`)

Hypothesis from the AB5-07 runs (16/16 PASS on `real-001`/`real-002`): the task descriptions state the required
rules, so agents implement a specification instead of diagnosing a bug. Each real task now has a second task file
with a description that states symptoms only: `tasks/real-001-bug/` (own bundle, see below; the missing-summary
case is not mentioned) and `tasks/real-002/task-bug-report.json` (same bundle as `real-002`; `real-002-bug`
(qualified request without limits accepted; `cpus: true` accepted; the float cases are not mentioned). The runner
stores the bound task file as the run's `task.json`. Agent runs: `experiments/real-001-bug.json`,
`experiments/real-002-bug.json`. Evidence: `RealTask2.test_bug_report_variant_shares_the_bundle_and_is_the_task_of_its_run`.

`real-001-bug` v1 (2026-10-11, same bundle as `real-001`) was defective: its description asked for complete usage
to be "fully priceable" and the golden fixtures to stay valid, while every hidden case used `cache_semantics:
"unknown"`, so rejecting the valid case (Codex) and allowing nulls under unknown semantics (Claude) were both
defensible readings. Its 8 grades are invalidated with that reason in `~/agent-benchmark-runs/real-001-bug-2026-10-11`.
v2 has its own bundle (`tasks/real-001-bug/`) whose cases use `cache_semantics: "separate"` and a description naming
that case; evidence `RealTask1Bug.test_bundle_and_reference_patches`.

# `real-003` from agent-harness `b8e1e90` (implemented)

Pattern proven by `real-001-bug` v2: a symptom-only report plus hidden cases where part of the fix must be inferred.
Source: `b8e1e90` "fix(contract): match the qualification job id as a whole token" (2026-10-06): evidence for job
`attempt-1` must not be accepted because it names `attempt-10`. Report: "a qualification for job X passed with
evidence written by job X0". Inferred part (hidden, not in the report): prefixes (`pre-X`), path/colon/dot/@/+
boundaries, and legitimate occurrences (`X` followed by a quote, newline, space or comma) that must still pass.
`verify_qualification_evidence(doc, evidence_root)` reads files, so the base gets task-owned evidence fixtures
outside the patch scope (scope = `src/agent_harness/contract.py`), each case passing an absolute path under
`/workspace`. Limit: candidate code runs in the same container and could rewrite those fixtures at import; the
verdict still needs the expected outcomes, which never enter the container. Acceptance before any agent run: the
reference patches (real fix, no-op, substring-only fix, over-strict exact-line match) must each fail or pass as
designed, including one reference patch per plausible reading of the report.

Implemented as designed (`tasks/real-003`, fixtures rebuilt by `build_fixtures.py`). Reference outcomes: `good` PASS;
`noop` fails 4; `digit_only` fails letter/prefix/hyphen; `word_boundary` (`\b`) fails only the hyphen case, which needs
the ID alphabet inferred from the contract; `overstrict` (job id alone at line end) fails the quoted and parenthesised
contexts. Evidence: `RealTask3.test_bundle_reference_patches_and_visible_checks`. Agent run: `experiments/real-003.json`.

# `real-004` from agent-harness `9e01ec4`

Source: `9e01ec4` "fix(contract): bind qualification evidence to its job and review subject" (2026-10-06, MIT); base =
parent `bb2cf18`. Symptom-only report: a report copied from another job, relabelled and re-signed, still passed.
Inferred (not stated): every passing check's evidence must name the job (not just one), and the review evidence must
name the reviewed report's subject. Fixtures in `base/bench_fixtures/` (reproducible via `build_fixtures.py`), other
reference patches via `build_references.py`. 5 hidden cases; reference outcomes: `good` PASS; `noop` fails 3;
`job_only` fails the stale review subject; `job_any` fails the check without the job; `overstrict` fails the JSON
context. Evidence: `RealTask4.test_bundle_reference_patches_and_visible_checks`. Agent run: `experiments/real-004.json`.

# `real-005` from pypa/packaging `2aada00`

First task from outside agent-harness: pypa/packaging (Apache-2.0 OR BSD-2-Clause), commit `2aada00` "fix: reject
empty arbitrary versions in requirements" (2026-10-06), base = parent `2c87a33`. Symptom-only report names
`Requirement("demo-lib===")`; the real fix is in the shared specifier regex, so `SpecifierSet("===")` must be
rejected too (inferred, not stated). Scope covers every file a plausible fix touches (`specifiers.py`,
`requirements.py`, `_parser.py`, `_tokenizer.py`) so a Requirement-only fix is judged on behaviour. Cases go through
`src.packaging.requirements` (`Requirement`, `SpecifierSet`, `_parse_requirement`); valid cases use the parser's
plain tuple so the answers are JSON. The project's tests need pytest, which the agents' sandbox lacks, so the visible
check is a stdlib smoke command. Reference outcomes: `good` PASS; `noop` fails 5; `requirement_only` fails both
SpecifierSet cases; `overstrict` (=== must start with a digit) fails both valid cases. Built by `build_task.py`.
Evidence: `RealTask5.test_bundle_reference_patches_and_visible_check`. Agent run: `experiments/real-005.json`.

`real-004` v1 (2026-10-11) was defective like `real-001-bug` v1: its description says evidence files must prove they
were produced for this report and its job, while the genuine fixtures' check evidence did not name the target and the
review evidence did not name the job. Both agents rejected the genuine reports (all 4 completed trials), a defensible
reading that no reference patch covered. Those grades are invalidated with that reason. v2 names target and job in
every genuine evidence file (the review also its subject) and adds the reference patch
`every_file_target_and_job`, which fails only `stale_review_subject`. Rule kept for every task: build the reference
patches from the description *before* the hidden cases are final, one per plausible reading, and check that the
genuine cases pass under all of them.

## Status after the 2026-10-11 runs

- `real-004` is **withdrawn**. In v2 both agents again rejected the genuine reports, this time by inventing their own
  provenance formats (Claude: a report-binding digest required in every evidence file; Codex: JSON evidence envelopes
  with a subject). "Evidence must prove it was produced for this report" admits many incompatible designs, and raw-log
  fixtures cannot satisfy any of them, so the task has no single correct answer. Its v2 grades are invalidated with
  that reason; the bundle stays for the record and `experiments/real-004.json` is removed.
- `real-005` v3 adds packaging's `.gitignore` to the base. Without it, `__pycache__/*.pyc` written by the agent's own
  Python runs entered the sealed diff (the harness diff honours the workspace's ignore rules) and failed the scope
  check; 3 Claude grades of the v2 run are invalidated for that reason. The agent-harness bases already had a
  `.gitignore`. Rule added: every base tree must ship the project's ignore rules for build artefacts.

# `real-006` from pypa/packaging `d3e7f5d`

Commit `d3e7f5d` "fix(version): reject non-string versions consistently" (2026-07-08); base = parent `9a11fba` with
`.gitignore`. The report names a float (`Version(2.5)` raises a bare TypeError). At the base, numbers, `None` and
dicts fail with TypeError but lists take another path and fail with AttributeError, so a fix that only catches
TypeError misses them (inferred, not stated). Cases go through `src.packaging.utils` (`Version`,
`canonicalize_version` as a string-valued guard); arguments are JSON. Reference outcomes: `good` PASS; `noop` fails 6;
`float_only` fails 5; `catch_typeerror` fails only the two list cases; `coerce_to_str` fails float and int. Built by
`build_task.py`. Calibration run first (`experiments/real-006-calibration.json`), then `experiments/real-006.json`.

`real-006` result (2026-10-11): 8/8 PASS for both agents. Its description added a general rule ("invalid input must
always raise InvalidVersion"), which states what was meant to be inferred. Rule from now on: the description is the
symptom with one example and nothing general.

# `real-007` from pypa/packaging `f14a093`

Commit `f14a093` "fix(specifiers): scope ~= groups with (?a:...)" (2026-08-12). The `~=` branch of the specifier
regex is compiled with IGNORECASE, so in Unicode mode `ſ` matches `s` (post release) and `ı`/`İ` match `i` (pre
release `preview`). The report shows only `~=1.0.poſt1`, with no general rule; the pre-release cases are inferred.
The dev group has no Unicode case-folding match and is not tested. Valid `SpecifierSet` cases expect the driver's
own `TypeError` (constructed, not JSON-serialisable), because the parser-based guards never reach the Specifier
regex; a reference patch removing IGNORECASE passed until these cases were added. Reference outcomes: `good` and
`ascii_flag_global` (a different correct fix) PASS; `noop` fails 5; `post_only` fails the two pre cases;
`no_ignorecase` fails the upper-case RC/DEV cases. Calibration first (`experiments/real-007-calibration.json`).

`real-007` result (2026-10-11): 8/8 PASS for both agents. Local inferences (another group of the same regex, another
exception path of the same function) are solved every time; only a rule that is not visible next to the fixed code
(`real-001-bug`) has discriminated so far.

# `real-008` from python-semver `1d51591`

Commit `1d51591` "Compare long numeric prerelease identifiers without integer conversion" (2026-10-01, BSD-3-Clause).
The report shows only a crash (ValueError from the 4300-digit int limit). The ordering that must hold is a SemVer
2.0.0 rule, not visible in the crashing line: digit-only identifiers compare numerically (a longer number is
larger), and numeric identifiers rank below alphanumeric ones. Reference outcomes: `good` and `int_limit_off` (a
different correct fix) PASS; `catch_as_string` fails only the magnitude case; `lexicographic_digits` fails the
magnitude case and the short `2` vs `10` guard; `reject_long` and `noop` fail all five long cases. The archive's two
test symlinks into `docs/` were removed (bundles allow no symlinks). Calibration first.

`real-008` result (2026-10-11): 8/8 PASS for both agents; the SemVer rule (a longer number is larger) is well known.

# `real-009` from python-semver `0aa17a3`

Commit `0aa17a3` "Handle malformed collection operands in Version comparisons" (2026-09-12, BSD-3-Clause). The
report shows only `Version.parse("2.0.0") == {}` crashing inside the library. The rule to infer is Python's data
model for an unsupported operand: `==` is False, `!=` True, and ordering raises the standard TypeError; the same
decorator already returns NotImplemented for other unsupported types. Operators are not module functions, so cases
run through the task-owned helper `base/bench_fixtures/ops.py` (outside the patch scope). Reference outcomes: `good`
PASS; `noop` fails 5; `catch_return_false` fails `!=` and every ordering case; `raise_typeerror` fails `==`/`!=`.
Calibration first (`experiments/real-009-calibration.json`).

`real-009` v1 calibration (2026-10-12): both agents failed the same three cases, lists with non-numeric parts. At the
base those raise ValueError, exactly like an invalid version string, which the library (also after the real fix)
keeps raising; catching only the structural TypeError was therefore a defensible reading. v2 keeps only malformed
structures (empty dict, unknown key) for `==`, `!=` and ordering, and adds the reference patch
`notimplemented_on_typeerror`, which must PASS. The two calibration grades are invalidated. Calibration is what
caught this before any full run.

`real-009` v2 result (2026-10-12): 8/8 PASS for both agents.

# `real-010` from python-humanize `823ad60`

Commit `823ad60` "Fix naturalsize() rounding rollover at unit boundaries" (2026-06-30, MIT). The report shows only
the default format: `naturalsize(999999)` gives "1000.0 kB". The rule to infer: the unit must follow what the
requested format actually rounds to (no rollover at `%.3f` for 999999 bytes, rollover at 999500 with `%.0f`), for
binary, GNU and negative sizes too. `src/humanize/_version.py` (built by hatch-vcs in the real package, git-ignored) and
the helper `bench_fixtures/hz.py` (puts `src/` on the path) are task-owned. Reference outcomes: `good` PASS; `noop`
fails 7; `threshold_default` fails 3; `round_one_decimal` fails 2. Calibration first.

`real-010` result (2026-10-13): 8/8 PASS for both agents.

# `real-011` from croniter `f64665e`

Commit `f64665e` "Fix \"{start}/{step}\" expanding to the whole field when start is the field maximum" (2026-08-01,
MIT). The report shows only the minute field (`59/15 * * * *` runs at :00/:15/:30/:45). Inferred: the same defect in
the hour, day-of-month, month and day-of-week fields, and croniter's deliberate, project-specific convention, stated
only in a code comment, that an explicitly written equal range such as `JAN-JAN` (also `JAN-JAN/2`) means the whole
cycle. The obvious fix "an equal range is one value" repairs every reported field and breaks that convention. The
grading container has no network, so python-dateutil 2.9.0.post0 and six 1.17.0 are vendored with their licenses in
`base/bench_fixtures/vendor`; cases run through `bench_fixtures/cron.py` (next three runs as ISO strings). Reference
outcomes: `good` PASS; `noop` fails the five field cases; `equal_range_single` fails both whole-cycle guards;
`equal_range_with_step` fails `JAN-JAN/2`. Calibration first.

`real-011` result (2026-10-13): 8/8 PASS for both agents; both kept croniter's whole-cycle equal range.

# `real-012` from Python-Markdown `7c265bc`

Commit `7c265bc` "Ensure that unterminated HTML tags do not cause text to be dropped" (2026-10-05, BSD-3-Clause). The
report shows one code span with a path (`cmd 2</dev/null`) after which the rest of the document disappears. Inferred:
other unterminated end-tag shapes (a space in the name, a trailing slash, a later `>`), also outside code spans.
Python-Markdown has no dependencies and its core tests use unittest, so the visible check runs the project's own HTML
block and code-span tests. Reference outcomes: `good` PASS; `noop` fails 5; `slash_path_only` fails 3; `gt_lookahead`
fails 2. Calibration first.

## Correction (2026-10-17): `real-001-bug` v2 is ambiguous in one case

The `complete_without_summary` case has a second plausible reading that no reference patch covers. Its input has `usage_completeness: "complete"` and one `stream` event with integer units and no `summary`. ADR 0002 in the base says only that a summary, *if present*, is authoritative and that stream events are informational. Neither the base code nor its docs say that `complete` requires a summary. "Without a summary, the stream events are the usage" is therefore consistent with the docs, and patches that read it that way fail this case. Every real-001-bug FAIL in every run fails exactly this case. So real-001-bug v2 measures which of two defensible readings an agent picks, not whether its fix is correct.
The grades stay valid as records of that choice and are not invalidated, because the grader did what the task
specified. Results on this task are reported as a reading preference.

## `real-001-bug` v3 (2026-10-17)

The description and base are unchanged. Hidden cases (7):
- `complete_without_summary` is removed.
- `complete_stream_only_null_cache_read` is added: a stream-only result under `complete` with a null unit. Both readings
  reject it.
- `complete_summary_overrides_null_stream` is added: a summary with integer units next to a stream event with a null
  unit. It is valid because ADR 0002 makes a present summary authoritative.

Reference patches:
- `good` is the upstream fix and passes.
- `stream_fallback` passes. It is a Codex candidate from the 2026-10-14 run and implements the second reading.
- `noop` fails the three null cases.
- `wrong` fails the override case because it checks nulls in every event.
- `overstrict` fails the override and partial cases.

Manifests pinned to v2 stay as the record of the v2 runs and no longer validate. Evidence:
`RealTask1Bug.test_bundle_and_reference_patches`.

### v2 candidates re-graded against v3 (post hoc, descriptive)

All 222 valid v2 candidates were re-graded on the qualified target against the v3 bundle (offline, no new trials).
Script and records: `~/agent-benchmark-runs/regrade-real-001-bug-v3-2026-10-17/`.
- Codex: 144/144 PASS, all runs and arms included.
- Claude without an addendum: 37/112 PASS. 73 of the 75 FAILs reject `complete_summary_overrides_null_stream`: they
  check nulls in every event, including stream events that a present summary makes informational.
- Claude with an addendum: 32/34 PASS.
- Builder/reviewer pairs: 7/7 PASS. Nemotron: 0/2.

v3 was designed after the v2 runs. These numbers come from a case added afterwards, which no pre-registration
covered, so they are a hypothesis for a pre-registered v3 run and not a result.

Note (2026-10-18, from agent-harness): the upstream fix `2ada5ffe` added the rule to ADR 0002 together with the code
check: "complete requires a summary for every attempt with every unit an integer; otherwise the result is partial or
unknown". The task base is the tree before that commit, so it carries the earlier, ambiguous wording by design. v2's
hidden case took its rule from a documentation change that the agents never saw. v3 accepts both readings, which is
right for a task frozen at that point.

# `real-013` from mistune `2d26bc8` (implemented 2026-10-18)

Selection: an offline scan of 2026-06..10 fix commits in 22 pure-Python projects. Kept were commits that touch tests
and at most two source files, change no docs, and enforce a rule that the base already documents. For mistune, that
rule is CommonMark rules 9 and 10, whose spec examples ship in `tests/fixtures/commonmark.json`.

Report: one input (`*foo***bar*`) and its CommonMark output. Hidden cases (15):
- 9 bug cases where a partially consumed delimiter run must still use its original length: the remainder of a closer
  and of an opener, strong runs, mixed content;
- 6 guards.

Every expected value equals both the fixed tree and the CommonMark reference implementation (commonmark.py 0.9.1). No
case therefore depends on a mistune-only reading.

Reference patches (`build_task.py`):
- `good` (upstream) passes.
- `closer_only` and `opener_only` fail one side each.
- `no_rule` fails a guard from the spec.
- `noop` fails all 9 bug cases.

Evidence: `RealTask13.test_bundle_reference_patches_and_visible_checks`. Calibration manifest:
`experiments/real-013-calibration.json`, 1 trial per agent, not yet run.

# `real-014` from pypa/packaging `2602dd0` (implemented 2026-10-18)

Report: a requirement whose URL embeds an LF is accepted, and `str()` writes a second requirement line. Hidden cases
(11):
- 5 bug cases: CR and CRLF inside the URL, CRLF after it, and LF before a marker;
- 6 guards: trailing space or tab, markers, extras, a file URL, a plain specifier.

Only line breaks are tested. The base's tests already reject a line-break suffix, and the grammar's whitespace is
space and tab. Rejecting a form feed or a Unicode space is a choice the base does not document, so no case requires it.

Reference patches:
- `good` (upstream `\S+`) passes.
- `lf_only` fails the CR case.
- `strip_url` (truncating the URL) and `noop` fail all 5 bug cases.

Evidence: `RealTask14.test_bundle_and_reference_patches`. Calibration manifest: `experiments/real-014-calibration.json`,
not yet run.

# `real-015` from mistune `86f9fd1` (implemented 2026-10-18)

Report: with the table plugin, three lines of pipe-separated text become a table and the second line is lost. Hidden
cases (12):
- 7 bug cases: second rows that are not GFM delimiter rows (text, bordered text, one text cell, spaced dashes, colons
  only, a lone colon, equals signs);
- 5 guards: valid delimiter rows.

Each case is a table, or is not one, exactly as markdown-it-py's GFM tables decide. Single-dash and empty delimiter
cells are excluded, because mistune and markdown-it-py disagree on them.

Reference patches:
- `good` passes.
- `no_alnum` fails the 4 punctuation-only cases.
- `needs_dash` fails spaced dashes.
- `noop` fails all 7 bug cases.

Evidence: `RealTask15.test_bundle_reference_patches_and_visible_checks`. Calibration manifest:
`experiments/real-015-calibration.json`, not yet run.

## Calibration of `real-013`..`real-015` (2026-10-18, harness v0.11.0)

One trial per agent and task (`~/agent-benchmark-runs/real-01{3,4,5}-calibration-2026-10-18`): all 6 completed and
passed every hidden case. Median trial time was Claude 18-30 s and Codex 40-57 s. None of the three tasks
discriminated in calibration. The cases are spec-backed forms of the same bug, and both agents covered them without
being asked.

# `real-016` from agent-harness `91bb3e1` (implemented 2026-10-18)

Type: a rule stated only in the project's own documentation, the same type as `real-001-bug` v3. ADR 0002 in the
base says "A null unit always means unknown", and unknown is never 0. The fix commit changes no ADR, only one
work-packet line.

Report: an OpenCode run whose step has no cache field records no usage at all. Hidden cases (12):
- 6 bug cases: a missing cache object, a cache object missing `read` or `write`, an empty cache object, mixed steps,
  and reasoning tokens;
- 6 guards: malformed values still fail, an error event marks the run failed, and full counts are summed.

A `cache: null` step is excluded, because reading it as unknown or as malformed are both defensible.

Reference patches:
- `good` passes.
- `zero_fill` (missing count = 0, against the ADR) and `noop` fail all 6 bug cases.
- `absent_only` fails the two cases with a partial cache object.

Evidence: `RealTask16.test_bundle_reference_patches_and_visible_checks`. Calibration manifest:
`experiments/real-016-calibration.json`, not yet run.

## Calibration of `real-016` (2026-10-18, harness v0.12.0)

`~/agent-benchmark-runs/real-016-calibration-2026-10-18`:
- **Claude: FAIL on all 6 bug cases.** Its patch reads a missing cache count as 0 (`cache.get("read", 0)`), the reading
  ADR 0002 rules out.
- **Codex: PASS.**

Both trials were first left ungraded: the qualification probes timed out while another workload held the host load
near 460 (`warnings.log`). A `resume` graded them after the load fell. The task discriminated in calibration; a
pre-registered confirmatory run is the next step.

# `real-017` from agent-harness `e48a7f5` (implemented 2026-10-18)

A sibling of `real-016` with the same rule from ADR 0002 (a missing count is unknown, never 0), in the Codex parser.

Report: codex-cli 0.160 reports `cache_write_input_tokens`, but the parser always returns `cache_write_tokens` null.
Hidden cases (9):
- 4 bug cases: one turn, a sum over turns, a zero count, a failed turn;
- 5 guards, including two turns where only one reports the field: unknown, not a partial sum.

Malformed write counts and turns without `cached_input_tokens` are excluded as ambiguous.

Reference patches:
- `good` (upstream, which also changes the sandbox probe) passes.
- `zero_fill` (a missing field adds 0) fails the 3 guards with a missing field.
- `noop` fails the 4 bug cases.

Evidence: `RealTask17.test_bundle_reference_patches_and_visible_checks`. Calibration manifest:
`experiments/real-017-calibration.json`, not yet run.

## Calibration of `real-017` (2026-10-18, harness v0.12.0)

`~/agent-benchmark-runs/real-017-calibration-2026-10-18`: Claude PASS (19 s) and Codex PASS (47 s). The task did not
discriminate in calibration, so no confirmatory run is planned. The report names the new field, and both agents kept a
turn without it as unknown.

### `real-016` calibration: grading record and shared-host window

The run directory is append-only. The first, ungraded state of both trials is kept as recorded and was not
overwritten:
- `claude-sonnet-pinned/r1`: ungraded at 2026-10-18T20:45:42Z. Grading job `grade-17cc5087-f0397fd5` did not qualify
  (B1 and B8 `DockerCommandTimeout`, B10 container exit 137). Its qualification evidence is kept under
  `qualification/grade-17cc5087-f0397fd5`.
- `codex-sol-pinned/r1`: ungraded at 20:59:22Z under job `grade-17cc5087-3e4a7c4f`, for the same cause.
- Cause, confirmed by agent-harness: the shared host was running the harness's Showcase cutover rehearsal and an
  evaluation, with a load average of about 460.
- Both trials were graded later, as separate `grade` events after `run_resumed` (21:05:40Z), under the new job
  `grade-17cc5087-4df93ded`, with the host load at about 9-40.

From 2026-10-18 on, every grade record stores the host load at grading time (`isolation.host_load`, 1/5/15-minute
averages), and every ungraded warning in `warnings.log` names it too.
