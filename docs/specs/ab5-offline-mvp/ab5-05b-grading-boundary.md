# AB5-05b - grading boundary requirements for a qualified target

Status: draft; input to the Showcase AH5-04b qualification (Q01-Q16), mapped in agent-harness
`docs/specs/AH5-04b/grading-requirements.md`. Contract: B9 fits v1 (`result.artifacts[]`, sealed by digest); B8 and
B10 need contract v2 (harness ADR 0005, proposed: result `target`, request/result `limits`). Until a target qualifies,
model-written code stays ungraded on this machine; harness `ProcessBackend` is controlled, not a sandbox, and is
never used for grading.

Two phases: **E** (agent execution, writes the candidate patch) and **G** (grading: patch applied to `base/`,
candidate code executed). Requirements are for G unless marked E. Each line is meant to become a qualification
check with its own evidence.

## Measured baseline (`reference-001`, 5 grades of the known-good patch, 2026-10-06)

Wall 0.19 s per grade, CPU about 0.16 s, peak child RSS 16 MiB, bundle 4 KB, task `timeout_seconds` 30.
Python stdlib only; needs `git` (for `git apply`) and Python >= 3.9.

## Requirements

| ID | Requirement | Check |
|---|---|---|
| B1 (E) | Hidden material is absent from the execution sandbox: not mounted, not in image layers, not in any Git object/history, not reachable over the network, not in env | payload searches FS, history and env for a canary file planted in the hidden bundle; must not find it |
| B2 | Hidden expected values never enter the grading sandbox; only test inputs do (see B9) | canary expected value planted outside; payload cannot read it |
| B3 | Fresh sandbox per grade, destroyed afterwards; nothing persists between grades (no shared volumes, caches, `/tmp`) | grade 1 writes a marker file; grade 2 must not see it |
| B4 | Mounts: workspace (fresh copy of `base/` + patch) read-write; test inputs read-only; root FS read-only; `/tmp` tmpfs. No host home, no Docker socket, no SSH/GPG agent, no repository `.git` | payload lists mounts, probes the socket and agent paths |
| B5 | Network: none. No egress, no DNS, no cloud metadata endpoint; loopback only | payload attempts TCP/UDP/DNS/metadata; all fail |
| B6 | Secrets: environment is exactly what the grader passes (`PATH`, `HOME`=sandbox tmp, `PYTHONDONTWRITEBYTECODE`, `GIT_CONFIG_NOSYSTEM`, `GIT_CEILING_DIRECTORIES`); no inheritance from the launcher, no credential files in the image | canary set in the launcher env and in a host credential file; payload must not see either (extends `test_candidate_runs_without_the_callers_secrets`) |
| B7 | Unprivileged: non-root user, no capabilities, `no_new_privs`, default seccomp profile | payload tries setuid binary, `mount`, raw socket |
| B8 | Limits, enforced by the target, defaults per grade: wall = task `timeout_seconds` (`reference-001`: 30 s); 1 vCPU; memory 512 MiB hard, no swap; 64 PIDs; 256 MiB writable disk (workspace + `/tmp`); stdout+stderr captured up to 1 MiB, the rest dropped. On breach the whole sandbox is killed and the result names the limit that fired (`timeout`, `oom`, `pids`, `disk`) instead of a plain non-zero exit | payload exceeding each limit in turn; result reports which one |
| B9 | Trusted result channel: the target returns one bounded output file (up to 1 MiB) from the workspace to the caller after the sandbox is gone; the verdict is computed outside the sandbox | payload writes the file; caller receives exactly those bytes |
| B10 | Evidence per grade: target ID, digest of the passing qualification report, image digest, applied limits, which limit fired (if any), exit code. Stored in the grade record `isolation` field | present in the result for every grade |

The limit values are defaults for stdlib Python tasks with about 150x headroom over the baseline; a task may
declare tighter values in `task.json` later. A larger real task needs new measurements and values, not a silent raise.

## Benchmark-side change this enables (not a target requirement)

Today the verdict (exit code + `Ran N tests` on stderr) comes from the process that imports the candidate, so a
candidate can forge it (print `Ran 4 tests`, exit 0 at import). A sandbox does not prevent that. With B2/B9, the
grader runs the candidate on hidden inputs inside the sandbox, receives outputs through B9 and compares them with
the expected values outside. Until that exists, PASS from `patch-unittest` is valid only for authored reference
patches (the current `host_execution_allowed` rule).
