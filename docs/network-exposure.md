# Network exposure policy

This file is the source of truth for the v1 lab's intended network exposure.
Compose binds describe the desired Docker host publication. They do not prove a
Windows firewall rule, Docker/WSL forwarding behavior, router exposure, or
public reachability. Record effective reachability only through approved,
redacted T480/T16 evidence.

| Service | Desired Compose bind | Intended audience | Host policy dependency | What proves the effective state |
| --- | --- | --- | --- | --- |
| PostgreSQL + pgvector | `127.0.0.1:5432` | T480 host and governed controller operations | No LAN firewall exception is permitted for v1. | Resolved Compose configuration and listener show loopback; an approved T16 test confirms no direct LAN database path is required. |
| n8n | `127.0.0.1:5678` | T480 host and governed adapter only | No LAN firewall exception is permitted for v1. | Resolved Compose configuration and listener show loopback; n8n health is checked locally on the T480. |
| Health dashboard | `0.0.0.0:8080` by default | Trusted private-LAN status readers only | Windows must allow fixed TCP 8080 only on the Private profile. No router forwarding or public ingress is permitted. | Resolved Compose configuration, listener, fixed firewall-status operation, and an approved redacted T16 LAN retrieval together establish the intended result. |
| Ollama (MVP) | `0.0.0.0:11434` only after `ollama_lan_enable` | Trusted Private-profile local-subnet clients | Windows must allow the fixed TCP 11434 rule on the Private profile with `LocalSubnet` remote scope. This raw HTTP API has no TLS or authentication. | Resolved Compose configuration, fixed firewall/listener verification, and an approved redacted private-LAN request. |

`docker compose port <service> <port>` establishes the container port
publication reported by Docker. It cannot establish firewall profile, router
forwarding, public DNS, or actual access from another device. A dashboard
`0.0.0.0` bind is not an authentication or network-policy control; it relies on
the documented host Private-profile firewall rule and trusted-network boundary.

Keep PostgreSQL and n8n loopback-only. Do not add a direct desktop PostgreSQL
client path, public ingress, router port-forward, or a firewall exception for
either service. The dashboard and the deliberately unauthenticated Ollama MVP
API are the only LAN publications. Do not send secrets or customer-sensitive
prompts to Ollama through this endpoint, and do not expose it through a public
DNS name, tunnel, or router port forward.

## Evidence and change control

Before a live exposure change, capture the existing desired binding and
redacted effective reachability result, make one approved change, then capture
the same checks again. Retain only interface class and pass/fail in tracked
notes; do not record IP addresses, credentials, raw socket output, or customer
data. Revert the exact binding and firewall rule if the approved T16 result
does not match this policy.
