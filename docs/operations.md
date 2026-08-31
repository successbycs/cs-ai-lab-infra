# Operations

Run all commands from the repository root. First copy `.env.example` to `.env` and replace every placeholder. Inspect the resolved configuration with `docker compose config`, start the default services with `docker compose up -d`, and check them with `./scripts/health-check.sh`.

Use `docker compose ps` for status and `docker compose logs -f <service>` for troubleshooting. `docker compose down` stops and removes containers and the network but preserves named volumes. Do not add `-v` unless you deliberately intend to erase persistent data.

## T480 check routine

From the T16, run the governed `Healthcheck` operator command. It first proves the SSH/Windows/WSL route is available with strict host-key verification, then runs the `lab_health` service check. The service check verifies the Docker daemon, Compose configuration, PostgreSQL container health plus a real query and pgvector extension, the n8n and health-dashboard host health endpoints, and Ollama only when its optional profile is running. It also reports low disk or memory as warnings. No service is started or restarted. After the check, the fixed publishing function appends only a redacted status summary to PostgreSQL and regenerates the static dashboard page.

```bash
python3 scripts/t480_adapter.py Healthcheck
```

`Healthcheck` is case-insensitive, so `healthcheck` also works. It passes only when its control-path preflight, service-health check, and redacted dashboard publication pass. Its result contains a named list of all three stages. A passing result proves remote access from the T16 as well as the T480 checks. If it fails, capture read-only troubleshooting detail before choosing a recovery action:

Every transport result retains the audit-safe UTC `started_at` and `finished_at` fields and includes matching `started_at_nz` and `finished_at_nz` fields in Pacific/Auckland time, including the current NZST/NZDT offset.

```bash
python3 scripts/t480_adapter.py execute --operation lab_runtime_diagnostics
```

Run `lab_services_start --approve` only after reviewing the failure; it is deliberately separate from the check routine so monitoring cannot change the machine.

This routine is tracked as M7, [T480 operational health routine proven](../t480/prompts/m7-operational-health.md). M7 is complete only after an actual T16 preflight and `lab_health` run are recorded as local evidence; defining the routine is not proof that the T480 is currently reachable.

## T480 sign-in startup

The governed `startup_enable` T480 operation creates a Windows Scheduled Task named `CS AI Lab Start`. At the configured Windows user's sign-in, it starts Ubuntu WSL, waits for Docker, then runs `docker compose up -d n8n health_dashboard`; Compose starts the PostgreSQL dependency as well. The task retains a minimal `tail -f /dev/null` WSL process so the WSL instance and its Docker containers are not shut down immediately after startup. It starts the status-only private-LAN dashboard but does not expose n8n or start the optional Ollama profile. `startup_run` starts it immediately; `startup_disable` removes it.

## T480 power policy

The active Windows Balanced plan is configured on AC power with sleep and timed hibernation disabled, plus a no-action lid-close policy. The fixed `power_policy_status` adapter operation reads these settings; `power_policy_ac_always_on` applies them with explicit approval. Battery settings are deliberately unchanged. This prevents normal AC idle or lid use from stopping WSL and Docker, but it does not provide unattended recovery after a Windows restart. That requires the boot-triggered Local System task defined in M5; the current task is sign-in triggered.

`./scripts/update.sh` pulls and verifies the deliberately pinned images; it does not restart services. To upgrade, first edit `compose.yaml` to a reviewed version tag and matching digest, then run the script and `docker compose up -d` when ready. Back up PostgreSQL before impactful updates with `./scripts/backup.sh`.

## On-demand MP4 transcription

The MP4 transcriber is intentionally separate from this Compose stack. Its governed adapter workflow is documented in [the T480 operations contract](../t480/README.md#mp4-transcription-folder-flow). It uses no shared PostgreSQL, n8n, or Ollama service and creates no persistent transcription worker. The only durable state is its private model cache and the review artefacts produced for a requested video.
