# T480 setup

This repository deliberately does not install or deploy anything automatically. On the T480, install a supported Linux distribution, enable secure SSH access from the T16, install Docker Engine plus the Docker Compose plugin, and ensure the intended user can run Docker. Keep the machine on a trusted private network; v1 has no public ingress.

Clone this repository, then create the local configuration:

```bash
cp .env.example .env
chmod 600 .env
# Edit .env and replace every CHANGE_ME value.
./scripts/bootstrap.sh
docker compose config
docker compose up -d
./scripts/health-check.sh
```

The Compose images use explicit version tags and verified Linux/amd64 digests, making the initial deployment repeatable on the T480. When deliberately upgrading, change both the visible version tag and the matching verified digest, read release notes, back up PostgreSQL, run `scripts/update.sh`, and then restart with `docker compose up -d`.

The default stack starts PostgreSQL, n8n, and the status-only health dashboard. Ollama is intentionally optional. Start it only when ready to experiment with containerised local inference:

```bash
docker compose --profile ollama up -d
```

Alternatively, install Ollama natively on the host as described in [Ollama guidance](../ollama/README.md). Start with a small, quantised model and measure its behaviour; do not preload models merely because they are available.

## Private-LAN health dashboard

The default stack also starts a status-only health dashboard on port `8080`, bound by `HEALTH_DASHBOARD_BIND_ADDRESS` (default `0.0.0.0` for the trusted LAN). Apply the reviewed `postgres/migrations/001_health_dashboard.sql` migration to an existing T480 database with the approval-gated PostgreSQL adapter, then run `Healthcheck` from the T16 to publish the first result:

```bash
python3 scripts/postgres_pgvector_adapter.py apply-migration --migration-file 001_health_dashboard.sql --approve
python3 scripts/t480_adapter.py Healthcheck
```

Open `http://<T480-LAN-address>:8080` from a trusted LAN device. After explicit approval, configure and verify the fixed Private-profile-only Windows firewall rule with the governed adapter:

```bash
python3 scripts/t480_adapter.py execute --operation health_dashboard_firewall_enable --approve
python3 scripts/t480_adapter.py execute --operation health_dashboard_firewall_status
```

Do not port-forward the dashboard or expose it publicly. The page deliberately has no sign-in or control functions, so it displays only redacted service status, timestamps, and recommended actions.

## Windows host power policy

For the WSL-hosted T480 runtime, configure the active Windows plan while on AC power to never sleep, never use timed hibernation, and take no action when its lid closes. Use the governed `power_policy_status` operation to inspect this policy and `power_policy_ac_always_on` only with explicit approval to apply it. These operations do not alter battery-mode settings. The policy is an availability safeguard, not a substitute for the boot-triggered no-logon startup task required by M5.
