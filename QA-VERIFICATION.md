# QA verification

Use this checklist to plan and record verification for a repository change. It
does not authorize live operations; follow [AGENT-WORKFLOW.md](AGENT-WORKFLOW.md)
and the relevant component skill.

## Define the evidence

Before testing, record the requirement or risk, changed scope, expected result,
and safe test input. Use synthetic or anonymised data only. Do not put secrets,
private addresses, customer data, or raw host output in tracked evidence.
For an ExecPlan, record the same acceptance evidence in its `Validation and
Acceptance` and `Outcomes & Retrospective` sections.

## Select applicable checks

- Repository edits: inspect the diff and run the focused test, lint, syntax, or
  parser check for changed files. Run `make quality` for cross-cutting Python,
  shell, JSON, or test changes.
- Compose edits: run resolved configuration validation for the affected Compose
  project. Check that service binds and volumes retain their intended boundary.
- Network work: collect redacted before/after evidence. Confirm effective
  reachability through the permitted path; a Compose bind alone is insufficient.
- T480 operations: use the fixed adapter's preflight, execution, and verify
  operations. Do not treat a remote command exit status as service proof.
- Backup or recovery work: verify manifests and use the isolated recovery drill
  unless a specifically authorized live restore is required.
- n8n, Penpot, Plane, or AI workflow work: perform the component's documented
  end-to-end read, smoke, or execution check and confirm its access boundary.

## Record the result

For every applicable check, state one of: **passed**, **failed**, **not run**,
or **not applicable**. For a failure or omission, record the impact, safe next
step, and whether it blocks the intended release. Separate observed results
from assumptions and planned follow-up.

Use [release readiness](RELEASE-READINESS.md) when the verified change is
intended for an authorized deployment or operational release.
