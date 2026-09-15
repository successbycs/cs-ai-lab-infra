---
name: network-exposure-review
description: Review or change service bindings, firewall dependencies, and effective reachability under the lab exposure policy.
---

# Network exposure review

Use for ports, bind addresses, firewall rules, SSH relays, LAN access, ingress,
or reachability claims. Read [network exposure policy](../../../docs/network-exposure.md)
as the source of truth.

- Distinguish desired Compose publication from effective reachability: Docker
  configuration alone cannot prove Windows firewall, WSL forwarding, router, or
  public access behavior.
- Keep PostgreSQL and n8n bound to loopback. The status-only dashboard is the
  only documented LAN publication and depends on the fixed Private-profile
  firewall rule.
- Do not add public ingress, router forwarding, broad firewall rules, or a
  direct LAN database path without an explicit approved design and policy
  update.
- Before an authorized live change, capture redacted before evidence, make one
  scoped change, and capture comparable after evidence. Revert the exact
  change if the permitted access path does not match policy.
- Do not commit IP addresses, raw socket output, customer data, or credentials
  as evidence.

Use `docker compose config` to inspect desired bindings and the governed T480
adapter for host firewall status or authorized repair.
