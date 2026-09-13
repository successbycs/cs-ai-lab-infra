# Standalone static-web template

Copy this directory into the product repository. Each product owns its source, `site/` exports, licence records, tests, Compose files, and protected per-project environment file; this infrastructure repository only supplies the starting contract.

```bash
install -d -m 700 /home/chris/.config/cs-ai-lab/projects
install -m 600 .env.example /home/chris/.config/cs-ai-lab/projects/example-static-web.env
# Edit it: set a unique COMPOSE_PROJECT_NAME and a reviewed WEB_IMAGE.
docker compose --env-file /home/chris/.config/cs-ai-lab/projects/example-static-web.env config --quiet
docker compose --env-file /home/chris/.config/cs-ai-lab/projects/example-static-web.env up -d --wait web
docker compose --env-file /home/chris/.config/cs-ai-lab/projects/example-static-web.env ps
docker compose --env-file /home/chris/.config/cs-ai-lab/projects/example-static-web.env down
```

The base file publishes no port. For a deliberately approved private ingress proposal, set a unique local port and use `docker compose --env-file /home/chris/.config/cs-ai-lab/projects/example-static-web.env -f compose.yaml -f compose.private-ingress.yaml up -d --wait web`; it is loopback-only by default. A real Caddy rollout must attach frontend services to its routing network, retain database-only project networks, specify routes and health checks, and include a rollback—none is deployed here.

`COMPOSE_PROJECT_NAME` must be unique per product. Pin and record `WEB_IMAGE` before rollout; rollback is restoring the prior reviewed product checkout (including `site/` exports and `nginx.conf`), setting `WEB_IMAGE` to the previously reviewed image reference, then running `docker compose --env-file /home/chris/.config/cs-ai-lab/projects/example-static-web.env up -d --force-recreate --wait web`. The default limits are a starting estimate only: validate under representative use against measured T480 headroom before rollout. Do not use `container_name`.

Expo Metro is temporary, project-local development tooling—not an always-on service. Private phone/tablet testing requires the device to reach the developer machine on the same private network (or an explicitly approved authenticated tunnel), the Metro port to be deliberately bound and firewall-scoped, and the session to be stopped after testing.
