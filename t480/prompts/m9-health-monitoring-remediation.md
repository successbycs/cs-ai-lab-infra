# M9 execution prompt — health monitoring review remediation

Execute after M7 has its required evidence. M9 remediates the incomplete M8 implementation; it does not make M8 proven without M8's own evidence.

1. Run `python3 scripts/t480_adapter.py Healthcheck` and `python3 scripts/t480_adapter.py Healthreport`. Review only the ignored controller files: `.t480-healthcheck.local.jsonl`, `.t480-healthcheck.latest.json`, `.t480-healthcheck.transitions.local.jsonl`, and `.t480-healthcheck.weekly-report.local.md`.
2. Verify that the result reports service lifecycle facts, bounded startup grace, pgvector evaluation, exposure policy, capacity, revision state, digest pinning, startup task state, and firewall state. Healthcheck must not start, restart, update, or expose a service.
3. If the T480 checkout is dirty, stop deployment. Create a recoverable operator-approved snapshot before any checkout repair; do not use reset, clean, or overwrite commands against unknown local work.
4. Once the checkout is safely updated, apply `001_health_dashboard.sql` and `002_healthcheck_lifecycle.sql`, start the dashboard with the approval-gated service operation, and enable only the fixed Private-profile TCP 8080 firewall rule.
5. Review `monitoring/healthcheck-schedule.json`. It is deliberately disabled and must not be activated without a separate approval.
6. Run a real Healthcheck, retrieve `http://<T480-LAN-address>:8080` from the T16, and record concise redacted evidence in the ignored milestone ledger. Do not record addresses, credentials, raw logs, or database contents.

The dashboard remains status-only. PostgreSQL and n8n must remain loopback-only; do not create an exception to make the dashboard work.
