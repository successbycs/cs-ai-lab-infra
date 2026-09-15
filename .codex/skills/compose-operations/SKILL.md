---
name: compose-operations
description: Safely review, change, validate, and operate this repository's Docker Compose deployments.
---

# Compose operations

Use for changes to a Compose file, service lifecycle request, image update, or
container diagnosis in this repository. Read the relevant component README and
[network exposure policy](../../../docs/network-exposure.md) before changing a
published port or network.

- Validate configuration with `docker compose config --quiet` before applying
  it. Do not render resolved configuration: it can contain secret values.
- Preserve named volumes unless the user explicitly identifies the volume and
  authorizes destructive removal. `docker compose down` does not delete them;
  `down -v` does and needs explicit authorization.
- Do not broaden a bind address or add a published port as a workaround for
  connectivity. PostgreSQL and n8n remain loopback-only; the dashboard's LAN
  publication has its documented Private-firewall dependency.
- Scope lifecycle commands to the named project or service. A service start,
  stop, update, image pull, or container removal changes runtime state and
  requires user authorization.
- For image changes, retain pinning/digest policy used by the component and
  update its operator documentation when lifecycle behavior changes.

Run `docker compose config --quiet` for Compose edits and use `make quality` when the
change touches repository scripts or tests. Report the exact checks performed
and any live operation deliberately not run.
