# Architecture

The T16 is the interactive development machine; the T480 is the private, persistent Docker runtime. GitHub is the versioned hand-off point. This repository defines shared platform services; each agent, RAG assistant, or mobile backend belongs in its own application repository.

On AC power, the T480's active Windows power plan is configured for no sleep, no timed hibernation, and no lid-close action. This protects the runtime from ordinary desk use while preserving separate battery-saving settings. It does not itself prove no-logon recovery after a Windows reboot; that remains an M5 boot-task requirement.

## Service boundaries

PostgreSQL is reusable platform infrastructure for relational data, metadata, and vectors through pgvector. The included generic init script enables the `vector` extension only; it does not create product or customer schemas. Applications own their schemas and migrations.

n8n stores its operational data in PostgreSQL and is for experimenting with integrations, scheduling, human approval, and workflow orchestration. Ollama is optional and is a local inference runtime, not an application dependency.

## Docker networking

All services join the `internal` bridge network. A Docker service reaches another service by its name—for example, `postgres:5432` or `ollama:11434` when the optional profile runs. These are internal Docker addresses.

Published ports map a host address to a container port. n8n maps `127.0.0.1:5678` to its container port, so it is accessible on the T480 but not the local network. PostgreSQL and Ollama have no published ports. Host networking removes this isolation and is not used in v1.

## Model architecture

```text
Application or agent → provider/model interface → local runtime | self-hosted runtime | cloud API
```

Use task-based routing later: inexpensive local models for bounded classification or extraction where evaluation proves they are sufficient; stronger cloud models and human approval for complex or high-stakes work. See [model strategy](model-strategy.md).

## Portability

Containers, environment configuration, and persistent backing services make migration practical. In a cloud deployment, application containers can move to a container platform, PostgreSQL to a managed database, volumes to managed/object storage, and local inference to a GPU or hosted provider. The application contract should remain configuration, database connection strings, and APIs—not T480-specific paths or addresses. Details: [cloud portability](cloud-portability.md).
