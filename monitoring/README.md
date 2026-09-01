# Health monitoring

`monitoring.healthcheck_runs` and `monitoring.healthcheck_checks` hold redacted Healthcheck results in PostgreSQL. The fixed `monitoring.record_healthcheck(jsonb)` function accepts only the adapter-created summary, and `monitoring.health_dashboard_payload()` returns the latest 30 runs for rendering.

`dashboard/render_health_dashboard.py` turns that payload into a static page. The `health_dashboard` Compose service serves the page on private-LAN port 8080 but has no PostgreSQL credentials, control routes, logs, or service data. It can serve a stale last-known result during a control-path outage, which is intentional.

Apply `postgres/migrations/001_health_dashboard.sql` and then `002_healthcheck_lifecycle.sql` before the first publication on an existing database. The matching init files apply both automatically for a brand-new database volume. The second migration adds the redacted service start and restart facts used by the dashboard.
