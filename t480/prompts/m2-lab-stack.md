# M2 execution prompt — lab stack operational

```text
You are operating the private T480 AI Lab from the T16 workstation. M0 and M1 are proven. Execute M2 — lab stack operational.

Success is determined by a real T480 evidence bundle, not a milestone JSON record. The ledger may only reference the bundle path, timestamp, and hashes after `scripts/verify-m2-evidence.sh` succeeds.

Execution plan

1. Read-only: confirm the approved Git revision is available to clone, Docker/Compose availability, free storage, and that no existing lab stack, Compose volume, repository directory, or `.env` would be overwritten.
2. Explain the exact deployment plan and obtain approval before copying/cloning the repository, creating `.env`, pulling images, or starting services.
3. Create `.env` only on the T480 with strong locally generated secrets. Never print, commit, or transmit those values back to the T16.
4. Run `./scripts/bootstrap.sh` and `docker compose config --quiet` before starting services. Do not run plain `docker compose config`, because it may print resolved secrets.
5. Pull the Compose-pinned images deliberately with `docker compose pull`. Record the resolved image references and image IDs; stop on a failed pull or unexpected image reference.
6. With approval, run `docker compose up -d --wait --wait-timeout 180` for PostgreSQL and n8n only. Keep n8n loopback-bound and do not start Ollama. Stop if either health check does not become healthy within the timeout.
7. Run read-only post-start checks: `docker compose ps`, repository health check, n8n loopback health endpoint, PostgreSQL readiness, extension inspection, and an actual pgvector distance query.
8. PostgreSQL initialization files run only when its data volume is first created. If an existing volume lacks the `vector` extension, stop and obtain separate approval for the reviewed schema repair; do not apply ad-hoc SQL.
9. The operator manually opens the local n8n UI on the T480 and completes initial owner setup. Do not create or export an n8n API key during M2; that is a separate, approved workflow-adapter setup action.
10. The operator manually opens an interactive T16-to-T480 SSH/Ubuntu session and runs `./scripts/capture-m2-evidence.sh` from the deployed repository. This captures raw service outputs on the T480.
11. The operator runs `./scripts/verify-m2-evidence.sh evidence/M2/<timestamp>` and personally observes a passing result.
12. Only then record the evidence-bundle path, SHA-256 manifest, and operator observation in the milestone ledger and mark M2 proven.

Required raw evidence

- Resolved pinned image references and local image IDs are captured.
- `docker compose ps` shows PostgreSQL and n8n healthy/running.
- `./scripts/health-check.sh` succeeds.
- n8n returns a successful loopback-only health response.
- PostgreSQL accepts a query and reports the `vector` extension.
- PostgreSQL executes `SELECT '[1,0,0]'::vector <-> '[0,1,0]'::vector;` successfully.

Do not treat an AI summary, a JSON status field, a package-install result, or a container-created message as proof. Do not expose ports publicly, log secrets, use raw arbitrary SQL, or run destructive Docker commands.
```
