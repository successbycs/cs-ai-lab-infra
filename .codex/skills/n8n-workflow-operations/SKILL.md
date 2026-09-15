---
name: n8n-workflow-operations
description: Safely manage n8n workflows and the governed private n8n adapter without exposing the service or key.
---

# n8n workflow operations

Use for n8n workflow import, activation, execution checks, API access, or
n8n-specific recovery. Read [n8n guidance](../../../n8n/README.md) first.

- n8n remains T480 loopback-only. Use `scripts/n8n_adapter.py` through the
  proven private transport; do not make the API reachable by adding a port,
  tunnel, or generic request mode.
- The n8n API key is T480-only at its documented protected path. Do not copy it
  to the T16, repository, logs, or a workflow definition.
- Workflow import and activation mutate n8n and require explicit approval. Use
  the adapter's approval gate; do not substitute direct API calls.
- Treat adapter metadata and import success as transport evidence only. Verify
  an actual workflow execution and capture the required raw evidence bundle.
- Start with synthetic or anonymised AI Lab scenarios. Do not add
  unapproved customer data sources or automated external actions.

For workflow changes, validate JSON as appropriate, use adapter preflight, and
report whether execution-level evidence was obtained.
