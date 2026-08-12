# Customer Success AI Lab Infrastructure

A reproducible, local-first platform for learning to design, build, operate, and evaluate AI-enabled Customer Success systems. It is infrastructure in service of a professional goal: becoming a Customer Success leader who can lead the transition to AI-enabled and agentic operating models.

It is not a general-purpose home-server project. Every addition should answer: **does it help build, evaluate, or scale a Customer Success AI workflow?**

## Architecture

```text
T16 workstation                 GitHub                    T480 AI Lab
VS Code, Codex, Git ──push──> source of truth ──pull──> Docker Compose
                                                               │
                                                    ┌──────────┼──────────┐
                                                    │          │          │
                                                PostgreSQL    n8n     Ollama*
                                                + pgvector  workflows  local models
                                                    │                     │
                                                    └──── Customer Success applications ──── cloud model APIs

* Ollama is optional in Compose; native-host Ollama is the recommended first T480 setup.
```

The T16 is the development workstation. The T480 is a persistent, private runtime. GitHub carries versioned configuration between them. Individual Customer Success applications live in their own repositories and consume this platform through networked services and environment configuration. When on mains power, the T480's active Windows plan is configured not to sleep or hibernate and to ignore lid-close events; its battery policy remains independent.

## v1 services

| Service | Purpose | Exposure |
| --- | --- | --- |
| PostgreSQL + pgvector | reusable structured data and vector-search foundation | Docker network only |
| n8n | workflow and orchestration learning platform | `127.0.0.1:5678` only |
| Ollama (optional profile) | CPU-friendly local inference experimentation | Docker network only |

Persistent state is held in named Docker volumes. The database is intentionally not published to the host. See [architecture](docs/architecture.md), [T480 setup](docs/setup.md), [operations](docs/operations.md), and [model strategy](docs/model-strategy.md).

Track the real T480 setup journey in the [provisioning log](docs/t480-provisioning-log.md). It records commands and verified outcomes without storing credentials or private network details.

The future automation boundary is documented in the [T480 operations contract](t480/README.md): a small allowlisted read-only command catalog that can be consumed by a remote adapter without giving an AI unrestricted shell access.

## Quick lifecycle (on the future T480)

```bash
cp .env.example .env
# edit .env: replace both CHANGE_ME values
./scripts/bootstrap.sh
docker compose config
docker compose up -d
./scripts/health-check.sh
```

Open n8n locally on the T480 at `http://127.0.0.1:5678`. For an optional containerised Ollama runtime, use `docker compose --profile ollama up -d`; the recommended starting approach is documented in [ollama/README.md](ollama/README.md).

Useful operational commands:

```bash
docker compose ps
docker compose logs -f n8n
./scripts/backup.sh
./scripts/update.sh
docker compose down                 # stops services; named volumes remain
```

## Repository layout

```text
.
├── compose.yaml                 Docker Compose platform definition
├── .env.example                 safe configuration template
├── docs/                        architecture, operation, and learning material
├── postgres/init/               generic first-run database initialisation
├── postgres/backup/             ignored local database backup destination
├── ollama/                      local model runtime guidance
├── n8n/                         workflow guidance
├── proxy/                       reserved until private ingress is justified
├── monitoring/                  reserved until lightweight monitoring is justified
└── scripts/                     safe bootstrap, health, backup, update helpers
```

## Security and backups

`.env` never enters Git. Replace all placeholders before startup, keep ports loopback-only, and do not expose this v1 lab to the public internet. `backup.sh` writes timestamped PostgreSQL dumps outside the container to `postgres/backup/`; those files are ignored by Git. Follow the restore procedure in [backup and restore](docs/backup-restore.md).

## Roadmap

1. Foundation: this repository and reliable local operation.
2. RAG: a synthetic Customer Success knowledge assistant.
3. A human-approved CS workflow: classify, retrieve, assess risk, recommend, draft.
4. Orchestration and model routing.
5. Customer-data integrations using synthetic/anonymised data.
6. Repeatable CS-focused model evaluation.
7. AI-native Customer Success operating-model prototype.
8. Migrate one proven application to cloud infrastructure.

The detailed learning sequence is in [learning roadmap](docs/learning-roadmap.md). Before adding infrastructure, record the reason in [decisions](docs/decisions.md).
