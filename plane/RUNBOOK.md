# Plane runbook

This runbook operates the private Plane deployment defined by the root
`compose.yaml` and included `plane/compose.yaml`. It is for deployment and
operator support; it does not define application-board workflow, task schema,
or evidence acceptance.

## Boundaries

- The root Compose project is authoritative. It includes Plane with the ignored
  `plane/plane.env`; do not run the Plane compose file independently unless a
  reviewed procedure supplies the same protected environment context.
- Plane's proxy is declared loopback-only on the T480. The T16 must use an
  approved private access path; do not create public ingress, router forwards,
  or broad firewall exceptions.
- `plane/plane.env`, `plane/plane-access.local.env`, and the referenced API-key
  file are local-only. Never render `docker compose config`, print their
  contents, or put values in tickets, logs, or Git.
- Plane boards coordinate work but are not evidence or deployment authority.

## T16 access

From the T16, prepare the local access configuration from
`plane/plane-access.local.example.env`, keep it mode 0600, and use only the
bounded adapter:

```bash
python3 scripts/plane_t16_relay.py start --approve
python3 scripts/plane_adapter.py web-status
python3 scripts/plane_adapter.py list-projects
python3 scripts/plane_adapter.py open-browser --approve
```

`web-status` proves only the configured private web origin. `list-projects`
proves only the workspace API path and may return board metadata. Neither proves
container health, persistent data, firewall policy, or deployment correctness.

## Safe validation and status

Validate the complete deployment from the repository root without rendering
secret values:

```bash
docker compose config --quiet
```

This validates desired configuration only. A missing local root `.env` prevents
meaningful local resolution; do not substitute placeholder secrets merely to
make the command pass.

Use the governed, read-only Plane status operation from the T16:

```bash
python3 scripts/t480_adapter.py execute --operation plane_status
```

It verifies the fixed service set, dependency health, and loopback-only proxy.
The relay consumes its proxy-port result internally; do not copy runtime output
into Git or use arbitrary SSH/Docker commands as a substitute.

## Lifecycle

Starting, stopping, updating, recreating, or removing Plane services changes
runtime state and requires explicit user approval. Before an approved change:

1. Review the root Compose diff and validate with `docker compose config --quiet`.
2. Confirm all Plane images remain digest-pinned.
3. Identify affected persistent volumes (`pgdata`, `uploads`, Redis, RabbitMQ,
   logs, and proxy state) and the rollback/recovery path.
4. Use a project-scoped operation only; never remove volumes as incidental
   cleanup.

After an approved change, record non-secret service/health evidence using the
governed status path once it exists. A successful Compose command alone is not
acceptance evidence.

## Incidents and recovery

Start with the T16 adapter checks and the future governed T480 status operation.
Classify whether the failure is T16 transport, proxy/web access, application
service health, or persistent state before proposing repair. Preserve logs and
volumes; do not reset Plane databases, regenerate secrets, or delete volumes as
first-line troubleshooting.

Plane backup and restore procedures are not yet established in this repository.
New backup creation is paused while T480 disk capacity is expanded; see
[`BACKUPS-PAUSED.md`](../BACKUPS-PAUSED.md). Do not claim Plane recoverability
until a separate approved backup/restore plan has been implemented and tested.
