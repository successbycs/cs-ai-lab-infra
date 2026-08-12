# Next Codex session — resume here

## Current operating state

- M0 through M3 are proven with real T480 evidence bundles where required.
- n8n is running privately on the T480 at `127.0.0.1:5678`, using the reviewed and digest-pinned `1.123.65` image. PostgreSQL/pgvector and Ollama are also installed.
- The n8n adapter is enabled with an API key stored only on the T480 in a mode-600 file. Do not request, print, copy, or commit that key.
- A bounded n8n live file-write workflow has been created and verified. Its output is stored only in the dedicated n8n file volume.
- The active T480 Windows plan is configured on AC power not to sleep or use timed hibernation and to ignore lid-close events. Battery behaviour is unchanged.
- The existing `CS AI Lab Start` task is sign-in triggered. It is useful for supervised recovery but does **not** meet the no-logon boot recovery requirement.

## Current milestone work

M5, hands-off maintenance and recovery, is in progress. WSL liveness after the sign-in task has been observed, but M5 is not proven. The remaining work is:

1. Replace the sign-in task with a boot-triggered task that runs as Local System, starts the fixed WSL action, and keeps the private PostgreSQL plus n8n stack alive without Windows logon.
2. Perform and evidence a no-logon restart drill that returns Docker, PostgreSQL, and n8n healthy.
3. Define and verify Windows Update active hours and a maintenance window.
4. Capture Lenovo BIOS-update readiness, including BitLocker and AC/battery conditions; do not install firmware without a separate operator request.
5. Capture and independently verify the M5 raw evidence bundle before recording the milestone as proven.

M6, governed n8n upgrade, is in progress. A backup, reviewed target, security upgrade, and post-upgrade workflow execution have passed. Complete future update detection and the formal raw evidence bundle verification.

## First safe checks

From this repository on the T16, start with read-only checks:

```bash
python3 scripts/t480_adapter.py execute --operation power_policy_status
python3 scripts/t480_adapter.py execute --operation startup_status
python3 scripts/t480_adapter.py execute --operation docker_status
python3 scripts/postgres_pgvector_adapter.py preflight
python3 scripts/n8n_adapter.py preflight
```

Use only the fixed adapter operations. Do not use free-form remote commands, record credentials, or treat the local milestone ledger as proof in place of a raw T480 evidence bundle.
