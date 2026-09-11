# Autonomous Penpot Deployment and Integration Goal

```text
Complete the entire Penpot deployment and integration subproject autonomously on the T480 lab machine. Do not wait for human operator feedback, clarification, or confirmation. Inspect the existing lab environment, make safe decisions from these requirements, implement, test, diagnose, and iterate until the deployment is working.

Model allocation

- Use Terra-Medium for implementation: environment and repository discovery, Docker Compose, scripts, configuration, documentation, deployment, routine tests, and routine repairs.
- Use Astra for architecture/design, security and remote-access design, MCP design, configuration review, difficult diagnosis, and final acceptance review.
- Terra-Medium implements Astra’s recommendations. Escalate to Astra for persistent failures, security concerns, remote-access design, data durability, or material tradeoffs.

Objective

Deploy a fully working, persistent Penpot service in Docker on the T480, with the official remote-mode Penpot MCP service, secure private remote access, repeatable operations, and proven integrations for the Shamatha Timer and Pt Chev Beach repositories.

Deployment requirements

- Create an isolated `penpot` subproject with its own Docker Compose project, dedicated private Docker network, and persistent named volumes. Do not modify or connect it to existing lab stacks.
- Use official Penpot frontend, backend, exporter, and MCP images alongside PostgreSQL and Valkey. Pin versions and immutable image digests.
- Configure resource limits, restart policies, health checks, and bounded Docker log rotation.
- Keep all secrets out of Git. Generate strong secrets automatically into a mode-0600 environment file outside the repository; commit only a secret-free `.env.example`.
- Provide private remote access without anonymous public exposure. Prefer existing private-network facilities such as Tailscale. If unavailable, bind the service to localhost and use authenticated SSH port forwarding. Do not require purchasing a domain or manual third-party dashboard work.
- If private HTTPS/DNS is available, configure Penpot with its actual HTTPS public URI, secure cookies, and an appropriate reverse proxy.
- Configure the official Penpot MCP service in remote mode behind the same private access boundary.
- The MCP container must not have host filesystem mounts, Docker socket access, privileged mode, unnecessary capabilities, or writable host access.
- Create or document a dedicated Penpot automation identity and MCP-key lifecycle. If interactive account creation cannot be automated, leave all infrastructure operational and provide one exact, minimal post-deployment setup step without blocking other work.
- Enable only minimum MCP capabilities required for design and read-only inspection. Document the capability boundary and key rotation/revocation process.

Cross-repository integration

- Discover the local Shamatha Timer and Pt Chev Beach repositories. Preserve unrelated repositories and existing configuration.
- Make Penpot MCP available to both repositories’ development workflows using their established Codex/MCP configuration convention.
- If a repository has no existing convention, add `docs/penpot-mcp.md` and a clearly named secret-free MCP configuration template.
- Do not commit Penpot passwords, MCP keys, Tailscale keys, SSH private keys, or any credentials to either repository.
- Store live connection credentials only in protected local configuration or the existing lab secret-management location.
- Prefer separate least-privilege Penpot automation identities or separately rotatable keys for Shamatha Timer and Pt Chev Beach.
- Validate each repository independently through its configured MCP client or a repository-local smoke-test command. The test must authenticate and perform only a harmless read-only Penpot action.

Operational deliverables

- Provide scripts for bootstrap, preflight, deploy, start, stop, health, backup, restore test, persistence test, upgrade, rollback, resource report, and emergency disable.
- Emergency disable must stop Penpot without deleting persistent volumes.
- Write:
  - a concise Penpot README;
  - an operator runbook;
  - an MCP client configuration guide;
  - a security/architecture decision record;
  - repository-specific MCP integration docs for Shamatha Timer and Pt Chev Beach.

Autonomous operating rules

- Start by inspecting repository instructions, existing Docker services, network configuration, remote-access tools, and relevant local repository conventions.
- Do not ask questions. Choose secure, conservative defaults and record all material assumptions in the ADR/runbook.
- Preserve unrelated files, services, networks, and volumes.
- Never use destructive commands against broad paths, existing Docker volumes, or unrelated Compose projects.
- If an external credential or immutable third-party configuration is unavailable, implement the best fully testable local/private fallback, document the exact remaining action, and complete every other part of the work.
- Iteratively investigate and repair failures until tests pass. Use Astra for difficult problems rather than stopping early.

Definition of done

- All Penpot services are healthy and restart safely.
- The web UI responds and authentication is enabled.
- Database and asset data persist across a Penpot-only restart.
- Backup creation and an isolated restore test succeed without endangering live data.
- The service is not accidentally accessible from the LAN or public internet.
- The private remote-access method is documented and tested.
- Penpot MCP is reachable through the selected private access path and passes an authenticated harmless read-only smoke test when credentials can be provisioned non-interactively.
- Shamatha Timer and Pt Chev Beach each have a secret-free, documented, tested path to the private Penpot MCP service.
- Neither repository contains secrets.
- Astra’s final review finds no unresolved critical security, isolation, durability, operability, or integration issue.

Final handoff

Report the changed files, verification output, service access URL/path, remote-access method, MCP configuration templates, repository integration results, any remaining manual integration step, and exact recovery and emergency-disable commands.
```
