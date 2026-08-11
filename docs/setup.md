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

The default stack starts PostgreSQL and n8n. Ollama is intentionally optional. Start it only when ready to experiment with containerised local inference:

```bash
docker compose --profile ollama up -d
```

Alternatively, install Ollama natively on the host as described in [Ollama guidance](../ollama/README.md). Start with a small, quantised model and measure its behaviour; do not preload models merely because they are available.
