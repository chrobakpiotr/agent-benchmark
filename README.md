# agent-benchmark

Offline-first benchmark that compares agent configurations on an identical task: success rate from an
independent grader, wall time, and (later) cost of every attempt. Current state: **offline MVP with a fake
executor only** - no model is called, results say nothing about any real model.

Rules for agents: [AGENTS.md](AGENTS.md). Spec: [docs/specs/ab5-offline-mvp/spec.md](docs/specs/ab5-offline-mvp/spec.md).

```bash
pip install .                      # Python >= 3.9; pulls agent-harness pinned by commit (needs GitHub access)
agent-benchmark validate tests/fixtures/manifest-offline-001.json
agent-benchmark run tests/fixtures/manifest-offline-001.json --out runs/demo   # writes events.jsonl + report
agent-benchmark report runs/demo   # regenerate report.md / report.csv / summary.json from records only
agent-benchmark report runs/demo --pricing tests/fixtures/pricing-2026-10-05.json   # bind a dated price snapshot
agent-benchmark run tests/fixtures/manifest-reference-001.json --out runs/ref   # patch task, reference patches
agent-benchmark resume runs/demo [--replace-unknown]   # after a crash: reconcile, grade, continue
agent-benchmark invalidate runs/demo cfg-a/r1 --reason "..."   # correction record; never upgrades to PASS
python3 -m unittest discover -s tests
```
