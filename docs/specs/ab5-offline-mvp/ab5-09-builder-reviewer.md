# AB5-09 - builder/reviewer workflow (agent-cli)

Status: implemented offline (fake CLIs); no real run yet. Plan item "strategies builder/reviewer" after more tasks.

## Behaviour

- Config `workflow: "builder-reviewer"` requires `reviewer: {"cli": "claude"|"codex", "model": "<id>"}`; `reviewer`
  is forbidden otherwise and with the fake executor. `reviewer` is part of the config identity (config digest,
  `compare`).
- One trial = two contract requests through `harness_port.launch` on the **same workspace and diff base**: the
  builder (config CLI/model, prompt `agent_prompt(task)`), then, only if the builder `completed`, the reviewer
  (`reviewer` CLI/model, prompt = task text + visible checks + review instruction; nothing hidden). Each launch has its
  own evidence root (`evidence/<request_id>/`, outside the workspace) and `backend-notes.json`.
- The trial's candidate is the reviewer's sealed diff, cumulative from the base. If the builder did not complete,
  the reviewer is skipped and the builder's terminal is the trial's. The zero-spend preflight and the
  `PROVIDER_ERROR` stop rule apply to both launches.
- Recording: one `trial_started`/`trial_finished` per trial; `attempts` and usage events carry the role prefix
  (`builder:attempt-1`, `reviewer:attempt-1`), so tokens and cost sum over both launches. A reviewer launch is not a
  retry: first-attempt/after-retry PASS counts ignore `reviewer:` attempts.

## AC -> evidence (`tests/test_agent_cli_run.py`)

| AC | Test |
|---|---|
| both launches recorded, usage summed, attempts prefixed, cumulative candidate | `test_builder_reviewer_trial_records_both_launches_and_the_cumulative_candidate` |
| no reviewer after a builder error; run stops | `test_builder_error_skips_the_reviewer` |
| config rules | `test_reviewer_config_rules` |

Agent run (not yet executed): `experiments/real-001-bug-builder-reviewer.json` - Claude builds/Codex reviews and
Codex builds/Claude reviews on `real-001-bug` v2, 4 repetitions each, to compare with the single-agent 5/12 and 9/12.
