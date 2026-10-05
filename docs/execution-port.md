# Execution port: consumer requirements (AB5-01 -> AH5-02)

**Status: requirements, not a contract.** The shared execution schema is owned by the agent-harness agent (AH5-02).
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
| Usage events with identity (source, event/request ID), categories, units, completeness; `null` when unknown | No double counting of stream + summary; unknown != 0 | summary only, no event IDs |
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
