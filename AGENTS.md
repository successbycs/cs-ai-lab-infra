This repository is the source of truth for shared AI Lab infrastructure. The
T16 is the interactive development machine; the always-on T480 is the private
runtime. Other repositories may deploy applications to the T480, but they must
use this repository's documented operational boundaries and remain portable to
a future cloud runtime.

# Repository guidance

This repository defines a private, local-first AI Lab for projects built with
agent-assisted and conventional development.
Keep changes focused on enabling, evaluating, or operating the workflows; record material architecture decisions in `docs/decisions.md`.

Follow [the agent workflow](AGENT-WORKFLOW.md) to route a request from scope
assessment through implementation, review, and handoff. Read
[the architecture](docs/architecture.md) before changing a service boundary,
runtime role, network relationship, or portability assumption.
Use [QA verification](QA-VERIFICATION.md) to record evidence-based test
coverage and [release readiness](RELEASE-READINESS.md) before an authorized
deployment or operational release. Use [plans](PLANS.md) for material,
multi-step, or cross-component work.

## ExecPlans

An ExecPlan is required for a multi-step or multi-file change, a new feature,
refactor, cross-component operation, or work likely to take more than an hour.
Create it at `plans/<short-action-name>.md` from
[`plans/TEMPLATE.md`](plans/TEMPLATE.md), then read and follow
[PLANS.md](PLANS.md) in full. The ExecPlan is the durable source of execution
context: keep its progress, discoveries, decisions, and outcomes current at
every stopping point. `make quality` mechanically checks active ExecPlan
structure; a passing check does not replace acceptance evidence.

## Safety and secrets

- Never commit `.env`, `*.local.env`, tokens, credentials, browser profiles,
  private network addresses, database dumps, or generated runtime state.
- Preserve loopback-only bindings for PostgreSQL and n8n. The health dashboard
  is the only documented LAN-facing service; do not add public exposure or
  router port forwards without an explicit design and policy update.
- Treat the T480 as a private runtime and GitHub as the configuration source of
  truth. Do not make undocumented, environment-specific assumptions part of
  versioned configuration.

## Working conventions

- Read the nearest component README and relevant documentation before changing
  a service. Keep component-specific procedures beside that component.
- Prefer small, reversible changes. Update operator documentation whenever a
  command, configuration value, port, access path, or recovery procedure
  changes.
- Use safe templates and placeholders for configuration examples. Never place
  real secrets in shell output, logs, test fixtures, or documentation.
- Keep scripts non-interactive where practical, fail closed on missing required
  configuration, and bind network listeners as narrowly as possible.

## Verification

Run the repository quality checks after relevant changes:

```bash
make quality
docker compose config  # when Compose configuration changes
```

For a scoped script-only change, at minimum run its applicable syntax or unit
tests and report anything not run. Do not start, stop, update, or delete
runtime services or volumes unless the task explicitly calls for it.

## Repository skills

Load the smallest applicable skill from [`.codex/skills`](.codex/skills/) before
working in its domain. These skills provide component-specific operating
constraints; this file remains the repository-wide policy.

| Skill | Use for |
| --- | --- |
| [`compose-operations`](.codex/skills/compose-operations/SKILL.md) | Compose configuration, stack lifecycle, and service diagnostics. |
| [`t480-operations`](.codex/skills/t480-operations/SKILL.md) | Governed T480 operations through the allowlisted adapter. |
| [`secrets-and-config`](.codex/skills/secrets-and-config/SKILL.md) | Local configuration, protected secret files, and safe examples. |
| [`backup-and-restore`](.codex/skills/backup-and-restore/SKILL.md) | PostgreSQL backups, recovery bundles, and restore drills. |
| [`network-exposure-review`](.codex/skills/network-exposure-review/SKILL.md) | Port bindings, firewall effects, and exposure-policy reviews. |
| [`plane-administration`](.codex/skills/plane-administration/SKILL.md) | Shared Plane access and its local adapter. |
| [`penpot-mcp-operations`](.codex/skills/penpot-mcp-operations/SKILL.md) | Penpot MCP relay, browser attachment, and isolated stack operations. |
| [`n8n-workflow-operations`](.codex/skills/n8n-workflow-operations/SKILL.md) | n8n workflow management through the governed adapter. |
| [`workflow-design`](.codex/skills/workflow-design/SKILL.md) | Design governed AI and automation workflows before implementation. |
| [`execplan-management`](.codex/skills/execplan-management/SKILL.md) | Create, execute, update, and review living ExecPlans for substantial work. |
| [`quality-assurance`](.codex/skills/quality-assurance/SKILL.md) | Plan and execute test coverage for changes and workflow behavior. |
| [`infrastructure-review`](.codex/skills/infrastructure-review/SKILL.md) | Review proposed infrastructure changes for policy, safety, and operational gaps. |
| [`infrastructure-verification`](.codex/skills/infrastructure-verification/SKILL.md) | Proportionate repository, Compose, script, and adapter verification. |
