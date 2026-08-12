# Operations

Run all commands from the repository root. First copy `.env.example` to `.env` and replace every placeholder. Inspect the resolved configuration with `docker compose config`, start the default services with `docker compose up -d`, and check them with `./scripts/health-check.sh`.

Use `docker compose ps` for status and `docker compose logs -f <service>` for troubleshooting. `docker compose down` stops and removes containers and the network but preserves named volumes. Do not add `-v` unless you deliberately intend to erase persistent data.

## T480 sign-in startup

The governed `startup_enable` T480 operation creates a Windows Scheduled Task named `CS AI Lab Start`. At the configured Windows user's sign-in, it starts Ubuntu WSL, waits for Docker, then runs `docker compose up -d n8n`; Compose starts the PostgreSQL dependency as well. The task retains a minimal WSL process so the WSL instance and its Docker containers are not shut down immediately after startup. The task does not expose any ports or start the optional Ollama profile. `startup_run` starts it immediately; `startup_disable` removes it.

`./scripts/update.sh` pulls and verifies the deliberately pinned images; it does not restart services. To upgrade, first edit `compose.yaml` to a reviewed version tag and matching digest, then run the script and `docker compose up -d` when ready. Back up PostgreSQL before impactful updates with `./scripts/backup.sh`.
