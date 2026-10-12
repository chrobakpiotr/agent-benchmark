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
