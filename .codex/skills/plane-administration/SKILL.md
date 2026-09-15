---
name: plane-administration
description: Safely use or maintain the shared Plane access adapter and private Plane deployment configuration.
---

# Plane administration

Use for Plane access, its adapter, private origin configuration, or its Compose
deployment. Read [Plane access](../../../docs/plane-access.md) first.
For deployment or incident work, also read the
[Plane runbook](../../../plane/RUNBOOK.md).

- Use `scripts/plane_adapter.py` for shared T16-side access. It is intentionally
  limited to web status, workspace project listing, and explicitly approved
  browser opening; do not add generic HTTP, shell, or board-mutation modes.
- Keep `plane/plane-access.local.env` local and mode 0600. The API key stays in
  its protected referenced file and must never be copied or printed.
- A Plane board is coordination metadata, not proof authority. Application
  repositories retain task schema, scheduling, evidence, and acceptance.
- Do not weaken loopback bindings, create firewall exceptions, or public ingress
  to make Plane easier to reach; use the approved private transport.
- Validate Plane through the root composition with `docker compose config --quiet`:
  it supplies Plane's included `plane/plane.env` context. Do not render resolved
  configuration or validate `plane/compose.yaml` alone without that context.
  Preserve the service image pinning strategy.

Opening a browser or changing deployment state is external mutation; do it only
when the user has requested it and report the resulting non-secret status.
