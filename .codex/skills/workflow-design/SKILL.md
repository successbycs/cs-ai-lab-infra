---
name: workflow-design
description: Design governed AI and automation workflows before implementation in n8n or application code.
---

# Workflow design

Use when defining a new AI Lab workflow, automating a manual
process, or deciding whether a workflow is ready for implementation. This is
for the design and governance layer; use `n8n-workflow-operations` for
governed n8n changes.

Describe the intended outcome before selecting a model, tool, or orchestrator:

- Identify the trigger, inputs, data classification, system of record, and
  expected output or decision.
- Separate deterministic steps from judgment calls. State the human approval,
  review, or escalation point for consequential customer-facing or external
  actions.
- Define constraints: permitted tools and data sources, least-privilege access,
  time/cost limits, idempotency or duplicate handling, retry stopping point,
  and audit evidence.
- Specify failure behavior: unavailable dependencies, low confidence,
  malformed input, no-match retrieval, partial completion, and safe handoff.
- Define observable acceptance criteria and a synthetic or anonymised test
  scenario. Do not treat a successful model response as proof of a safe
  workflow.

Use the [learning roadmap](../../../docs/learning-roadmap.md) and
[architecture](../../../docs/architecture.md) when the design affects the lab's
scope or a new shared service. Record a material architectural decision in
`docs/decisions.md` before implementation.
