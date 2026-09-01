# T480 milestones

The lab uses a small evidence-first milestone system. A milestone is not proven because a document says it is complete; it becomes proven only when every acceptance check has a local evidence record, including at least one explicitly marked real-world execution check.

The tracked [milestone registry](milestone-registry.json) defines the work and acceptance checks. The ignored `.t480-milestones.local.json` file records real-machine results, so private host details and command output do not enter Git.

For M2 and later, the ledger is not proof. Run the milestone-specific capture script directly on the T480 to create a local raw evidence bundle, then run its verifier. The ledger records only a reference to the resulting bundle and operator observation.

## Commands

```bash
python3 scripts/t480_milestones.py status
python3 scripts/t480_milestones.py show --id M1
python3 scripts/t480_milestones.py start --id M0
python3 scripts/t480_milestones.py record-check --id M0 --check powerShell_available --result pass --evidence 'PowerShell and ssh.exe available on T16'
python3 scripts/t480_milestones.py add-evidence --id M1 --evidence 'Operator observed the M1 container proof directly.'
python3 scripts/t480_milestones.py prove --id M0
```

`status` is read-only. `show` displays a milestone's ordered execution plan, acceptance checks, and current state. `start` records local progress. `record-check` records the result and concise evidence for one defined check. `add-evidence` adds an operator-observed supplementary proof without changing a milestone's status. `prove` refuses to mark a milestone proven until all its checks have recorded a passing result and its dependencies are proven. Command results display UTC timestamps; individual evidence records retain their own `recorded_at` timestamp.

## Milestone sequence

| ID | Outcome |
| --- | --- |
| M0 | T16 control path proven |
| M1 | Docker runtime proven — [execution prompt](prompts/m1-docker-runtime.md) |
| M2 | Lab stack operational — [execution prompt](prompts/m2-lab-stack.md) |
| M3 | Recovery proven — [execution prompt](prompts/m3-recovery.md) |
| M4 | First governed n8n workflow — reserved in [next-session](next-session.md) |
| M5 | Hands-off maintenance and recovery proven — [execution prompt](prompts/m5-hands-off-maintenance.md) |
| M6 | Governed n8n upgrade proven — [execution prompt](prompts/m6-n8n-upgrade.md) |
| M7 | T480 operational health routine proven — [execution prompt](prompts/m7-operational-health.md) |
| M8 | T480 operational health monitoring proven — [execution prompt](prompts/m8-operational-health-monitoring.md) |
| M9 | Health monitoring review remediation proven — [execution prompt](prompts/m9-health-monitoring-remediation.md) |

M6's post-upgrade validation includes the `validation_integrity_corrections` subtask. It corrects stale M2 image evidence expectations, prevents unfiltered workflow-export metadata from reaching the n8n API, and makes the default test command reliably execute the adapter suite.

M7 adds a read-only operational routine after M2. It proves the T16 control path and verifies the required private services without treating an intentionally stopped optional Ollama profile as a fault or performing automatic recovery.

M8 hardens M7 into an operational monitoring control. It deliberately excludes backup freshness and recovery checks until a backup capability has been implemented and separately proven.

Do not record passwords, keys, private IP addresses, or unredacted service data in evidence text.
