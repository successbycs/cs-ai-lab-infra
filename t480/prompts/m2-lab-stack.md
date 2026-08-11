# M2 execution prompt — lab stack operational

```text
You are operating the private T480 AI Lab from the T16 workstation. M0 and M1 are proven. Execute M2 — lab stack operational.

Success is determined by a real T480 evidence bundle, not a milestone JSON record. The ledger may only reference the bundle path, timestamp, and hashes after `scripts/verify-m2-evidence.sh` succeeds.

Execution plan

1. Read-only: confirm the intended Git revision, Docker availability, free storage, and that no existing lab stack or `.env` would be overwritten.
2. Explain the exact deployment plan and obtain approval before copying/cloning the repository, creating `.env`, pulling images, or starting services.
3. Create `.env` only on the T480 with strong locally generated secrets. Never print, commit, or transmit those values back to the T16.
4. Run `./scripts/bootstrap.sh` and `docker compose config` before starting services. Stop on any unresolved configuration failure.
5. With approval, run `docker compose up -d` for PostgreSQL and n8n only. Keep n8n loopback-bound and do not start Ollama.
6. The operator manually opens an interactive T16-to-T480 SSH/Ubuntu session and runs `./scripts/capture-m2-evidence.sh` from the deployed repository. This captures raw service outputs on the T480.
7. The operator runs `./scripts/verify-m2-evidence.sh evidence/M2/<timestamp>` and personally observes a passing result.
8. Only then record the evidence-bundle path, SHA-256 manifest, and operator observation in the milestone ledger and mark M2 proven.

Required raw evidence

- `docker compose ps` shows PostgreSQL and n8n.
- `./scripts/health-check.sh` succeeds.
- n8n returns a successful loopback-only health response.
- PostgreSQL accepts a query and reports the `vector` extension.

Do not treat an AI summary, a JSON status field, or a package-install result as proof. Do not expose ports publicly, log secrets, or run destructive Docker commands.
```
