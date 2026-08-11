# Cloud portability

Keep application services stateless: build them as containers, configure them with environment variables, and put durable data in backing services. Never depend on T480 paths, a laptop hostname, or implicit `localhost` access.

PostgreSQL may move from the Compose volume to managed PostgreSQL with pgvector. Replace local file persistence with managed volumes or object storage, inject secrets from a cloud secret manager, and pass database URLs rather than changing application logic. Container ports become platform service ports; a reverse proxy or managed ingress supplies DNS, TLS, and authentication.

External APIs and model providers remain configuration choices. An application should expose health endpoints, use migrations, log structured events, and document its data ownership. These habits make a later move to Vercel, a VM, ECS, Azure, GCP, or another container platform a deployment decision rather than a rewrite.
