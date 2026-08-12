# Operations

Run all commands from the repository root. First copy `.env.example` to `.env` and replace every placeholder. Inspect the resolved configuration with `docker compose config`, start the default services with `docker compose up -d`, and check them with `./scripts/health-check.sh`.

Use `docker compose ps` for status and `docker compose logs -f <service>` for troubleshooting. `docker compose down` stops and removes containers and the network but preserves named volumes. Do not add `-v` unless you deliberately intend to erase persistent data.

## T480 sign-in startup

The governed `startup_enable` T480 operation creates a Windows Scheduled Task named `CS AI Lab Start`. At the configured Windows user's sign-in, it starts Ubuntu WSL, waits for Docker, then runs `docker compose up -d n8n`; Compose starts the PostgreSQL dependency as well. The task retains a minimal `tail -f /dev/null` WSL process so the WSL instance and its Docker containers are not shut down immediately after startup. The task does not expose any ports or start the optional Ollama profile. `startup_run` starts it immediately; `startup_disable` removes it.

## T480 power policy

The active Windows Balanced plan is configured on AC power with sleep and timed hibernation disabled, plus a no-action lid-close policy. The fixed `power_policy_status` adapter operation reads these settings; `power_policy_ac_always_on` applies them with explicit approval. Battery settings are deliberately unchanged. This prevents normal AC idle or lid use from stopping WSL and Docker, but it does not provide unattended recovery after a Windows restart. That requires the boot-triggered Local System task defined in M5; the current task is sign-in triggered.

`./scripts/update.sh` pulls and verifies the deliberately pinned images; it does not restart services. To upgrade, first edit `compose.yaml` to a reviewed version tag and matching digest, then run the script and `docker compose up -d` when ready. Back up PostgreSQL before impactful updates with `./scripts/backup.sh`.
