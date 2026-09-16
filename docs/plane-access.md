# Shared Plane access adapter

`scripts/plane_adapter.py` is the shared, T16-side Plane access adapter for
application repositories. It is deliberately smaller than an application
board client: it verifies the Plane web origin, lists workspace membership, and
can open the T16 browser after explicit approval. It cannot create projects,
states, tasks, evidence, or worktrees, and has no generic HTTP or shell mode.

Each application retains ownership of its board identity, project/task schema,
task scheduling, evidence and acceptance. A Plane board is never proof
authority.

## Local setup

Copy `plane/plane-access.local.example.env` to
`plane/plane-access.local.env` and set mode `0600`. `PLANE_ORIGIN` is a
private T16-reachable Plane origin and `PLANE_WORKSPACE_SLUG` selects the one
workspace whose projects can be listed. `PLANE_API_KEY_FILE` references an existing
owner-only file containing the configured variable; the adapter never copies
or logs that token.

```bash
python3 scripts/plane_t16_relay.py start --approve
python3 scripts/plane_adapter.py web-status
python3 scripts/plane_adapter.py list-projects
python3 scripts/plane_adapter.py open-browser --approve
```

When the configured origin is a plain T16 HTTP loopback URL, start the fixed
local relay first. It listens on that configured loopback port and transports
each connection through strict-host-key-checked SSH to Plane's private T480
WSL loopback; it does not open a T480 firewall port or change Plane's loopback
publication. `start` and `stop` require `--approve`; `status` is read-only.

For deployment lifecycle, safe validation, diagnostics, and recovery limits,
use the [Plane runbook](../plane/RUNBOOK.md).
