# AB5-00..02 - offline MVP: manifest -> fake run -> grade -> report

Status: draft.
Source plan: `agent-benchmark-agent-plan-2026-10-05.md` (AB5-00, AB5-01, AB5-02) + `master-agent-handover-2026-10-05.md`.

## Behaviour

- `agent-benchmark validate MANIFEST`: validates the manifest and its bound task bundle; exit 0 OK, 2 rejected.
- `agent-benchmark run MANIFEST --out DIR`: `DIR` must not exist. Plans trials (balanced, seeded), runs each
  sequentially through the **fake** executor, seals candidates by content digest, grades them, appends events
  to `DIR/events.jsonl`, then writes the report.
- `agent-benchmark report DIR`: regenerates `report.md`, `report.csv`, `summary.json` from recorded files only;
  byte-identical on repeat; never runs the executor or the grader.

## Records kept separate

execution outcome (`completed/timeout/cancel/error/unknown`) | harness completion claim (`success/failure/null`) |
grade (`PASS/FAIL/INVALID`, or none when there is no candidate) | measurement quality (`complete/partial/unknown`).

## Acceptance criteria -> evidence

| AC | Evidence |
|---|---|
| AB5-00 build/install/help outside checkout | clean venv install + `--help` from empty cwd (manual smoke); `test_package.test_help_from_empty_cwd` |
| AB5-00 no side effects/model calls at import | `test_package.test_import_has_no_side_effects` (socket blocked, empty cwd stays empty, no API keys) |
| AB5-00 Git rules and read order available locally | `AGENTS.md`, `docs/constitution.md` |
| AB5-01 unknown version / missing identity / wrong bindings / contradictions rejected | `test_schema.ManifestValidation.*`, `TaskValidation.*`, `EventValidation.*` |
| AB5-01 unknown usage valid | `test_unknown_usage_is_valid` |
| AB5-01 fixture round-trip stable | `test_round_trip_is_stable` |
| AB5-02 known PASS/FAIL/timeout mix gives hand-computed counts | `test_pipeline.test_counts_match_hand_computed_oracle` |
| AB5-02 report regenerated without executing models | `test_report_regenerates_identically_without_executing` |
| AB5-02 fake clearly labelled | `test_fake_is_labelled_everywhere` |

## Oracle for `tests/fixtures/manifest-offline-001.json` (computed by hand)

| config | scripted trials | expected |
|---|---|---|
| cfg-a | good / good / noop (harness claims success) | 3 completed; PASS 2, FAIL 1; 2/3, Wilson95 [0.2077, 0.9385]; 1 harness-success-not-PASS; usage 1 complete, 1 partial, 1 unknown; known tokens in 150 / out 20 |
| cfg-b | good / timeout / error | 1 completed, 1 timeout, 1 error; PASS 1, 2 ungraded; 1/3, Wilson95 [0.0615, 0.7923]; usage 1 complete, 2 unknown; known tokens in 200 / out 40 |

## Assumptions (to confirm)

1. A trial without a candidate is **ungraded**, not FAIL; it still counts in the operational-success denominator.
2. INVALID = the candidate cannot be bound to its sealed digest (missing or modified after seal).
3. `retry_policy.max_attempts` must be 1 and `exclusions` must be `[]` until AB5-03/04 define them.
4. Synthetic task has no repository/base SHA; `environment` states this explicitly.
5. Cost is `null` (unknown) in every report until AB5-04 adds pricing snapshots.

## Out of scope

Live/paid model calls, pricing, retries, dedup/resume (AB5-03), real task and isolated grading host (AB5-05a/b),
harness adapter (AB5-06), dashboard, database, queue.

## Next tasks (packets not generated; DAG is linear)

AB5-03 trial integrity/resume (see `ab5-03-integrity.md`) -> AB5-04 cost + statistics (see `ab5-04-cost.md`). AB5-05a: see `ab5-05a-grader.md`.
AB5-06a consumes contract v1 (see `ab5-06a-contract.md`); AB5-06b (harness launch) waits for AH5-03b.
