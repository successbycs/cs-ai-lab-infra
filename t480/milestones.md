# T480 milestones

The lab uses a small evidence-first milestone system. A milestone is not proven because a document says it is complete; it becomes proven only when every acceptance check has a local evidence record, including at least one explicitly marked real-world execution check.

The tracked [milestone registry](milestone-registry.json) defines the work and acceptance checks. The ignored `.t480-milestones.local.json` file records real-machine results, so private host details and command output do not enter Git.

## Commands

```bash
python3 scripts/t480_milestones.py status
python3 scripts/t480_milestones.py show --id M1
python3 scripts/t480_milestones.py start --id M0
python3 scripts/t480_milestones.py record-check --id M0 --check powerShell_available --result pass --evidence 'PowerShell and ssh.exe available on T16'
python3 scripts/t480_milestones.py prove --id M0
```

`status` is read-only. `show` displays a milestone's ordered execution plan, acceptance checks, and current state. `start` records local progress. `record-check` records the result and concise evidence for one defined check. `prove` refuses to mark a milestone proven until all its checks have recorded a passing result and its dependencies are proven. Command results display UTC timestamps; individual evidence records retain their own `recorded_at` timestamp.

## Milestone sequence

| ID | Outcome |
| --- | --- |
| M0 | T16 control path proven |
| M1 | Docker runtime proven — [execution prompt](prompts/m1-docker-runtime.md) |
| M2 | Lab stack operational |
| M3 | Recovery proven |

Do not record passwords, keys, private IP addresses, or unredacted service data in evidence text.
