# AB5-03 - trial integrity and resume

Status: draft. Event schema bumped to `agent-benchmark/event/v2`
(adds `event_id`, separate `usage` events, `trial_started.replaces`, `trial_finished.source`, `run_resumed`,
`correction`). v1 is rejected; no v1 data existed outside temporary test runs.

## Rules (implemented in `report.reduce_events`, `runner.resume`, `runner.invalidate`)

1. Ledger is append-only. Reading folds it; the first record wins and every disagreement is listed under
   `integrity.conflicts` (report shows `integrity: N conflict(s)`), never silently applied.
2. Same `event_id` + same body = re-delivery, ignored. Same `event_id` + different body = conflict.
3. One terminal per trial. A later terminal (any `event_id`) is a `conflicting_terminal` conflict.
4. Usage: dedup by `usage_event_id` per trial; per attempt a `summary` supersedes `stream` events; stream events
   are summed as deltas. Usage for an attempt not in the terminal's `attempts` is a conflict and ignored.
5. `trial_started` is written before launch. `resume`:
   - started without terminal -> terminal `outcome=unknown, source=reconciliation`; never re-executed;
   - `--replace-unknown` -> replacement trial `<trial_id>/xN` with new `request_id`, `replaces=<trial_id>`;
     both count in the operational-success denominator;
   - sealed candidate without grade -> graded now; planned but never started -> executed;
   - nothing pending -> error, nothing appended.
6. Corrections: only `invalidate` (needs a reason). Effective grade becomes INVALID; the original grade record and
   `original_grade` stay visible. No correction can produce PASS.

## AC -> evidence (`tests/test_integrity.py`)

| AC | Test |
|---|---|
| duplicate event does not double usage | `test_redelivered_event_is_counted_once`, `test_stream_and_summary_overlap_not_double_counted` |
| conflicting terminal does not overwrite | `test_conflicting_terminal_does_not_overwrite`, `test_same_event_id_different_body_keeps_first` |
| interrupted trial stays visible, not re-run | `test_crash_between_launch_and_record_is_not_rerun` |
| replacement has new identity and link | `test_replacement_gets_new_identity_and_link` |
| crash before/after record | `test_crash_before_launch_record_runs_the_trial`, `test_crash_after_terminal_before_grade` |
| corrections never upgrade, history kept | `test_invalidate_lowers_result_and_keeps_history`, schema test for `action` |

## Assumptions (to confirm)

- A summary is authoritative for its attempt; whether harness summaries may overlap streams is open for AH5-02.
- Usage lost in a crash after the terminal record stays unknown (no backfill).
- Replacement is opt-in per resume call, not automatic (no predeclared retry policy yet).
