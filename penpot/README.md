# Private Penpot on the T480

This directory defines a separate, private Penpot deployment for shared design
work. It does not modify or join the existing `cs-ai-lab`, OpenWorker, Neo4j,
product, Vercel, Supabase, or Google Apps Script runtimes.

The live endpoint is deliberately limited to `http://127.0.0.1:9001` on the
T480. It is not approved for LAN or Internet exposure. An operator may use it
at the T480 or through an authenticated SSH local-forward. See [ADR 0001](ADR-0001.md),
the [operator runbook](RUNBOOK.md), and [MCP access design](MCP.md).

## Inventory

| Container | Purpose | Persistent storage | Published port | Limit |
| --- | --- | --- | --- | --- |
| `penpot-frontend` | UI, API and MCP reverse proxy | `penpot_assets` | `127.0.0.1:9001` → `8080` | 0.5 CPU / 256 MiB |
| `penpot-backend` | Penpot application/API | `penpot_assets` | none | 1.5 CPU / 2 GiB |
| `penpot-exporter` | render/export worker | none | none | 1 CPU / 1 GiB |
| `penpot-mcp` | official multi-user MCP bridge | none | none; proxied at `/mcp/stream` | 0.5 CPU / 512 MiB |
| `penpot-postgres` | Penpot database | `penpot_postgres` | none | 1 CPU / 1 GiB |
| `penpot-valkey` | websocket/task coordination | `penpot_valkey` | none | 0.25 CPU / 192 MiB |

All containers use `restart: unless-stopped`, 10 MiB × 3-file JSON log
rotation, the isolated `penpot-private_penpot_internal` bridge, and pinned image
tags plus immutable manifest digests. Only frontend publishes a host port.

## Configuration and secrets

`compose.yaml` is reproducible configuration. `.env.example` documents names
only. `scripts/bootstrap.sh` creates the live mode-0600 environment at
`/home/chris/.config/cs-ai-lab/penpot.env`. It generates a unique database
password and 512-bit master secret. Never copy that file into Git, tickets,
screenshots, chat, or a design file.

Registration, email delivery, telemetry, and secure cookies are disabled for
the initial localhost HTTP phase. Password login, access tokens, MCP, and the
profile-management PREPL are enabled. Before any non-local exposure, replace
the HTTP/cookie posture with approved private HTTPS and review SMTP/invitation
handling.

## Sources

The deployment follows Penpot's official self-hosted Compose architecture and
MCP plugin model:

- <https://help.penpot.app/technical-guide/getting-started/>
- <https://help.penpot.app/technical-guide/configuration/>
- <https://help.penpot.app/mcp/>
- <https://github.com/penpot/penpot/releases/tag/2.17.2>

Versions and digests were resolved on 2026-09-11. Review upstream release
notes and security advisories before changing any pin.
