# Execution port: consumer requirements (AB5-01 -> AH5-02)

**Status: requirements, not a contract.** The shared execution schema is owned by the agent-harness agent (AH5-02);
its v1 proposal and this repo's consumer review are at the end of this file.
agent-benchmark does not define a competing variant. Until a versioned AH5-02 contract exists, the runner uses one
fake port (`runner.fake_execute`) with the semantics below, and every record produced through it is labelled
`executor.kind = "fake"`, `isolation_track = "fake-offline"`. When AH5-02 publishes a version, AB5-06 replaces the
fake with one adapter over the public API at a pinned version, and these requirements are checked against it.

## What the benchmark needs from one execution request

| Need | Why | Fake today |
|---|---|---|
| Caller-supplied `request_id`, echoed back | Dedup/reconcile after a crash between launch and record (AB5-03) | yes |
| Backend `execution_id` (null if never launched) | Bind events and usage to one execution | yes (`fake-exec-<request_id>`) |
| Child attempts with own IDs and per-attempt outcome | Every retry/reviewer call counts towards trial cost | 1 attempt |
| Terminal outcome enum: `completed / timeout / cancel / error / unknown` | Kept separate from grade | yes |
| Optional harness completion claim (`success / failure / null`) | Reported, never used as grade | yes |
| Candidate artifact bytes or reference + digest | The grader binds to the sealed digest | bytes |
| Usage events with identity (source, event/request ID), categories, units, completeness; `null` when unknown | No double counting of stream + summary; unknown != 0 | one `summary` event per attempt; ledger already handles `stream` + `summary` (AB5-03) |
| Requested vs resolved model, CLI/SDK + version | Part of config identity | not applicable |
| Declared capabilities (cancel, usage, isolation level) | Unsupported capability must be visible, not silently skipped | not applicable |
| Cancellation that resolves to a real terminal state | Cancelled trials must not vanish | not applicable |

## Non-goals for the benchmark side

- No lease, grant, supervisor or authority store; those stay in agent-harness.
- No import of private harness modules; public API only (AB5-06).
- Harness "done" never substitutes for the benchmark grade.

## Open points for AH5-02 (to agree, not decided here)

1. Usage event identity and whether a final summary may overlap stream events (dedup key).
2. Candidate transport: bytes vs. workspace reference + digest; who seals.
3. How child attempts and their usage are attributed to the parent request.
4. Capability declaration shape and the error for unsupported capabilities.

## Consumer review of AH5-02 execution contract v1 (agent-harness `1f07db4`, ADR 0002 "Proposed")

Read-only review; nothing in agent-harness was changed. Their `tests.test_contract` ran locally: 10 tests OK
(Python 3.9.6, `PYTHONDONTWRITEBYTECODE=1`). This is not an approval of the contract.

Covered as required: caller `request_id` + `request_digest` binding; `execution_id` null when never launched;
`attempts[]` with own IDs; `outcome` separate from `completion` and from the (consumer-owned) grade;
`cancel_requested` vs `drain`; declared capabilities with rejection codes; usage dedup key
`(execution_id, event_id)`, at most one `summary` per attempt and summary authoritative over `stream` (same rule
as the benchmark ledger, AB5-03); no events => usage unknown, never 0; no prices in the contract.

Findings / questions for the contract owner:

1. **Null units under `usage_completeness: complete`.** The success fixture is `complete` with
   `cache_read_tokens: null` and `cache_write_tokens: null`. For cost, null must mean either "0 / not
   applicable" or "unknown"; today it is ambiguous and changes whether a trial is fully priced. Proposal: under
   `complete` every unit is an integer (0 when the provider reports none); null only under `partial/unknown`.
2. **Pinning.** AB5-06 must consume a pinned artefact (version + digest). There is no published wheel; a local
   path or unpushed SHA is not reproducible for another checkout. Needs a decision on the distribution form.
3. **Launch API.** No launch/cancel API exists yet (ADR: AH5-03b/AH5-04b). AB5-06 is BLOCKED on it; the
   benchmark keeps its fake port until then.

Benchmark-side delta to apply in AB5-06 (not now, to avoid a second variant of the same fields):
`harness_completion success/failure` -> `completion accepted/rejected`; new outcome `rejected` (never launched;
counts in the operational denominator as non-PASS, excludable); candidate bytes -> reference `{path, sha256, size}`
copied from the evidence root into the benchmark's content-addressed store after verifying digest and size;
`usage_event_id/usage` -> `event_id/units` with `cache_write_tokens`; cache handling moves from the pricing flag
`input_includes_cache_read` to the event's `cache_semantics` (`unknown` with non-zero cache tokens => not fully
priced) and pricing gains a `cache_write` rate.
