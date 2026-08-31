# M8 execution prompt — T480 operational health monitoring

You are operating the private T480 AI Lab from the T16 workstation. Execute M8 — T480 operational health monitoring proven.

## Outcome

Evolve the read-only M7 `Healthcheck` command into a dependable operator control. It must show the current condition clearly, retain safe local history on the T16, distinguish startup from failure, identify drift and capacity risks, and make the next safe action obvious.

## Scope and explicit exclusion

- Include: control-path availability; Docker and service health; PostgreSQL monitoring tables; a status-only private-LAN HTML dashboard; startup grace; restart counts; WSL/startup-task liveness; n8n/PostgreSQL exposure; Docker volume capacity; checkout and image-digest drift; state-transition events; local history; scheduled-run configuration; and a weekly local report.
- Exclude: backup freshness, backup integrity, and restore verification. The lab has no backup capability yet; add those only in a later, separately approved milestone.
- Outbound notifications remain disabled. They require a separately selected and approved delivery destination.

## Safety boundaries

- Healthcheck, history, report generation, and scheduled execution are read-only with respect to T480 services. They must never start, restart, recreate, update, expose, or stop a container.
- Keep raw service logs, credentials, private addresses, database data, API keys, and workflow content out of Git and the health-history files.
- Preserve UTC fields for audit use and add Pacific/Auckland fields for operator use.
- Use the fixed adapter surface only. Any task registration or notification configuration must be a separate fixed, approval-gated operation.

## Required execution order

1. Implement and test normalized Healthcheck results, reviewed `monitoring` PostgreSQL tables, a static HTML rendering function, and redacted T16-local `.t480-healthcheck.local.jsonl` plus `.t480-healthcheck.latest.json` files. Document retention and rotation.
2. Add bounded readiness retries, explicit required/optional service policy, restart/start-time evidence, and operator-safe recommended actions.
3. Add Windows startup-task/WSL, exposure, volume-capacity, revision, and image-digest checks. Classify every result as PASS, WARN, FAIL, or SKIP.
4. Apply the reviewed health-dashboard migration to the existing T480 database. Start the restart-managed dashboard through Compose and the T480 startup path, then publish only the normalized Healthcheck result to PostgreSQL and render the dashboard from those tables. Expose the dashboard—not n8n or PostgreSQL—to the private LAN on TCP 8080, restricted to the Windows Private firewall profile. Verify the page from the T16.
5. Add transition-only local events and a weekly report generated from the redacted history. Do not emit external alerts.
6. Design the fixed scheduler interface and review it before any activation. It must run the same read-only Healthcheck command and preserve no secrets in task arguments or logs.
7. Run the complete real Healthcheck from the T16, inspect its local output, history, report, and LAN dashboard, then record concise evidence in the ignored milestone ledger. Do not create a failure by disrupting a healthy lab just for this milestone.

## Success criteria

- Every result shows UTC and NZ time fields, per-check status, durations, and safe next actions; its normalized status data is retained in PostgreSQL and rendered without credentials or raw logs on the private-LAN dashboard.
- Remote-control failures remain visible because history is written on the T16.
- The check distinguishes a starting service from an unhealthy one, reports restart/capacity/exposure/drift signals, and leaves optional Ollama explicitly healthy or skipped.
- The dashboard is restart-managed, included in the T480 startup procedure, available from the T16 over the trusted LAN, and limited to redacted status data on TCP 8080.
- No backup assertion, external notification, or service mutation is part of M8.
- The scheduled-run design and weekly report are reviewable, and M8 evidence proves a real T16-to-T480 run.
