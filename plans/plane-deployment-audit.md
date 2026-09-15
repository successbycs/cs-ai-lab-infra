# Audit the Plane deployment and prepare a remediation plan

This ExecPlan is a living document. Maintain it in accordance with
[`PLANS.md`](../PLANS.md). Keep `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

Status: complete

## Purpose / Big Picture

Establish whether the Plane deployment is configured and operating as intended,
without exposing credentials or bypassing the governed T480 boundary. The
outcome is a non-secret audit result: conformant findings or a concrete,
prioritized remediation plan that can be approved separately.

Scope: static review of Plane Compose/configuration, safe T16-side Plane
adapter checks, and identification of missing T480 evidence. Non-goals:
changing Plane services, images, firewall rules, secrets, workspaces, boards,
or data during the audit.

## Progress

- [x] (2026-09-15 00:00Z) Created the audit ExecPlan and confirmed Plane is
  included by the root Compose project with `plane/plane.env`.
- [x] (2026-09-15 00:00Z) Performed safe static configuration review without
  printing resolved credentials.
- [x] (2026-09-15 00:00Z) Attempted the bounded T16 Plane adapter read-only
  checks; the Windows PowerShell request failed without exposing configuration.
- [x] (2026-09-15 00:00Z) Compared available evidence to acceptance criteria
  and created a remediation ExecPlan for confirmed control gaps.

## Surprises & Discoveries

- The current Plane skill recommends standalone `plane/compose.yaml` validation,
  but the deployed composition is rooted in `compose.yaml`, which includes
  Plane together with `plane/plane.env`. Standalone validation can therefore
  assess a different interpolation context.
- The T480 command catalog has no dedicated Plane read-only health operation.
  A full runtime audit cannot be claimed until a governed read-only evidence
  path exists or an approved equivalent is identified.
- All 13 tracked Plane images are digest-pinned and the proxy is declared on
  T480 loopback. The tracked Plane services have no Compose health checks.

## Decision Log

- (2026-09-15) Decision: perform static and T16 adapter checks first, then
  report any missing live T480 evidence as a gap rather than using arbitrary
  SSH/Docker commands. Rationale: the adapter is a deliberate safety boundary.
- (2026-09-15) Decision: do not make remediation changes in this audit. A
  confirmed gap becomes a separate approval-gated plan. Rationale: deployment,
  image, secret, and data changes have operational consequences.

## Outcomes & Retrospective

Static findings: the root composition includes the protected Plane environment,
all 13 images are digest-pinned, and the proxy publishes only to loopback.
However, no Plane service has a health check, there is no governed T480 Plane
status operation, and the T16 adapter's Windows PowerShell request failed.
`plans/plane-deployment-remediation.md` now defines the approval-gated fix.
No Plane service, secret, binding, or data was changed.

## Context and Orientation

The root `compose.yaml` includes `plane/compose.yaml` and provides
`plane/plane.env` as the include environment file. `plane/plane.env` is ignored
because it carries deployment credentials. `docs/plane-access.md` defines the
separate T16-side `scripts/plane_adapter.py`; it can check the configured private
web origin and list workspace projects, but cannot mutate Plane.

The audit must distinguish desired Compose configuration from effective T480
runtime state. Static review can establish digest pinning, declared loopback or
private access paths, health checks, and persistent volumes. It cannot prove
the actual Windows firewall, running containers, data persistence, or browser
reachability. A Plane board is coordination metadata, never deployment proof.

## Plan of Work

Milestone 1 reviews the tracked deployment definition. It traces the root
Compose include, checks image digests, volume declarations, health/dependency
rules, port bindings, and secret boundaries without rendering protected values.
Proof is a redacted configuration review tied to exact files.

Milestone 2 collects bounded live evidence from the T16 adapter. It checks the
private web origin and workspace listing only when the local protected access
configuration exists. Proof is the adapter's non-secret status result; failure
is recorded as an evidence gap, not a reason to weaken exposure.

Milestone 3 compares collected evidence with the intended architecture. If
conformant, record the limited confidence and remaining runtime gap. If
sub-standard, create a remediation ExecPlan with root cause, risk, smallest
safe change, exact verification, rollback, and required approval gate.

## Concrete Steps

1. Read `compose.yaml`, `plane/compose.yaml`, `docs/plane-access.md`,
   `scripts/plane_adapter.py`, and the network policy. Use static source review
   and `docker compose config --quiet` only; do not render resolved settings.
2. Verify every Plane image is digest-pinned, the root include supplies the
   intended environment context, secrets are ignored, and service ports/volumes
   match their documentation. Record exact file references, never values.
3. If `plane/plane-access.local.env` exists and passes the adapter's local
   ownership/mode checks, run `python3 scripts/plane_adapter.py web-status` and
   `list-projects`. These are read-only. If it is absent or invalid, record the
   missing T16 evidence; do not read or print its contents.
4. Inspect the T480 catalog for a Plane status operation. If absent, record the
   inability to assert live container/volume/firewall state and prepare a
   separate proposed plan for a narrow read-only status operation.
5. Compare results with the acceptance criteria. Write a remediation ExecPlan
   under `plans/` only for confirmed gaps, and stop before implementation.

## Validation and Acceptance

- Root-level Compose validation completes without outputting protected values.
- Static review establishes the composition relationship, pinned images,
  persistent state declarations, and declared exposure boundaries.
- T16 adapter evidence, if configuration is present, establishes only the web
  origin and workspace API path; it does not prove T480 runtime health.
- The result explicitly labels static facts, observed live evidence, and
  remaining unknowns.
- Any confirmed deficiency has a separate, approval-gated remediation plan;
  no live Plane mutation occurs in this audit.

## Idempotence and Recovery

All audit commands are read-only and safe to repeat. The audit does not start,
stop, update, remove, or recreate Plane services, volumes, or data. If access
configuration is absent, stop at the static review; do not create credentials,
change bindings, or use an ungoverned remote shell.

## Artifacts and Notes

The audit records findings in this plan or a non-secret tracked note, with
source paths and bounded status results only. Protected Plane environment files,
API keys, local config, raw host output, and workspace data remain outside Git.
