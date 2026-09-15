# Release readiness

Use before an authorized deployment, service update, configuration cutover, or
operational release. This is a decision checklist, not approval to change a
live service. Follow [AGENT-WORKFLOW.md](AGENT-WORKFLOW.md) and obtain explicit
user authorization for the release operation.

## Required decision inputs

- Scope and owner are clear: affected services, configuration, data, and the
  intended runtime target are identified.
- The change has a reviewed, versioned diff. Secrets, private topology, local
  state, backups, and generated evidence are not included.
- When the change required an ExecPlan, its milestones, decision log, and
  validation outcomes are current; incomplete work is explicitly recorded.
- Applicable checks in [QA verification](QA-VERIFICATION.md) are passed, or
  any omission/failure is explicitly understood and accepted by the release
  decision-maker.
- Documentation reflects changed access paths, ports, commands, operations,
  recovery steps, and material architectural decisions.
- The rollback or recovery action is known, scoped, and safe. Persistent
  volumes and live data will not be removed as incidental release cleanup.

## Additional gates by change type

- **Compose or image change:** resolved Compose configuration is valid; image
  selection/pinning is intentional; health and persistence checks are planned.
- **Network change:** it preserves [network exposure policy](docs/network-exposure.md),
  with redacted effective-reachability evidence and an exact rollback path.
- **T480 change:** it uses a documented allowlisted adapter operation and has
  required explicit approval.
- **Backup/recovery change:** manifest verification and isolated recovery proof
  establish the claim; no live restore occurs without separate authorization.
- **Penpot, n8n, or Plane change:** component-specific access controls, local
  secret handling, and end-to-end acceptance checks remain intact.

## Release decision and handoff

Record the release decision, authorized operator, release identifier or commit,
checks performed, remaining risk, and rollback trigger in the appropriate
local or tracked non-secret operational record. After an authorized release,
verify the intended service behavior and report what was actually observed;
never infer a successful release from a deployment command alone.
