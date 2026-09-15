---
name: infrastructure-verification
description: Select and run proportionate verification for infrastructure, scripts, Compose files, adapters, and operational evidence.
---

# Infrastructure verification

Use after a repository change or when reviewing whether a proposed change is
adequately verified. Start with the narrowest checks that exercise the altered
surface, then expand for cross-component or high-risk changes.

- Run `make quality` for repository-wide Python, shell, JSON, or test changes.
- For Compose changes, run `docker compose config --quiet`; do not print the
  resolved configuration because it can contain secrets. Validate the root
  project when it composes a component, such as Plane; use a component file
  alone only when its documented environment context is supplied.
- For a single script, run its syntax check and focused unit test where
  available. Validate scripts without printing local configuration or secrets.
- Separate static configuration validation from live runtime verification.
  Do not claim firewall, remote reachability, persistence, backup recovery, or
  workflow behavior from a local parse or container status alone.
- Live operations may start, stop, mutate, or access private systems. Run them
  only within the task's authorization and use the component's governed path.
- Report commands/checks, outcome, scope, and meaningful omissions. Do not
  include secrets, private addresses, raw host output, or customer data.

Use the component skill for acceptance criteria: network changes need effective
reachability evidence, restores need manifest and isolated-drill evidence, and
n8n/Penpot changes need their respective end-to-end checks.
