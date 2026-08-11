# Architecture decisions

| Decision | Rationale | Revisit when |
| --- | --- | --- |
| Docker Compose, not Kubernetes | smallest portable operational surface for v1 | a concrete learning or scale requirement appears |
| Local-first, cloud-portable | cheap experimentation without a cloud rewrite | an application has proven value |
| PostgreSQL in Docker with pgvector | combines structured customer context and vector search | a workload demonstrates a different data need |
| Separate application repositories | keeps this platform focused and application lifecycles independent | a shared component genuinely belongs here |
| Ollama is initial local runtime | simple CPU-only experimentation | a task needs another runtime or hardware changes |
| Models and providers are swappable | model landscape and task needs change rapidly | maintain continuously |
| Retain frontier cloud models | capability and reliability may matter for high-impact CS work | evaluation supports a different policy |
| Task-based routing is a future goal | optimise quality, cost, latency, and privacy per task | evaluation harness exists |
| No public exposure in v1 | avoids premature security and operations burden | explicit private-access design is approved |
| Secrets remain outside Git | protects credentials and enables environment-specific configuration | never as a default |
| Customer Success AI is the project filter | infrastructure serves the professional learning mission | a change has clear transferable value |
