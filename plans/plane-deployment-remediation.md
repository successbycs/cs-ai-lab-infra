# Add verifiable Plane deployment health controls

This ExecPlan is a living document. Maintain it in accordance with
[`PLANS.md`](../PLANS.md). Keep `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

Status: active

## Purpose / Big Picture

Address the confirmed Plane audit gaps so an operator can verify that the
private Plane deployment is healthy through governed, non-secret evidence. The
outcome is a bounded T480 Plane status operation and documented health checks,
validated without exposing Plane credentials or broadening its loopback bind.

Scope: Plane Compose health checks, a narrow read-only T480 adapter operation,
its catalog/tests/documentation, and T16 adapter diagnostics if evidence shows
they are needed. Non-goals: changing Plane images, services, databases,
workspaces, credentials, firewall rules, ports, or public access.

## Progress

- [x] (2026-09-15 00:00Z) Received the static audit findings and created this
  remediation plan.
- [x] (2026-09-15 00:00Z) Defined dependency health criteria from Plane's
  official Compose test stack without changing the deployment.
- [x] (2026-09-15 00:00Z) Implemented and tested a read-only governed Plane
  status operation and Compose dependency health checks.
- [x] (2026-09-15 00:00Z) Obtained approved T480 runtime evidence; Plane passed
  while the independent T16 adapter failure remains a separate repair target.

## Surprises & Discoveries

- The static audit found all images digest-pinned and proxy loopback-bound, but
  no tracked Plane health checks and no T480 Plane status operation.
- T16 `web-status` failed at its Windows PowerShell request boundary. The
  failure message does not identify whether the issue is browser transport,
  origin availability, or local PowerShell execution; do not guess.
- Plane's official test Compose uses `pg_isready`, `valkey-cli ping`, and
  `rabbitmq-diagnostics -q ping` for its dependency services. It does not
  establish a stable unauthenticated API or frontend health endpoint here.

## Decision Log

- (2026-09-15) Decision: add only read-only Plane health evidence before any
  repair or deployment mutation. Rationale: the audit cannot prove live health,
  but it does not establish that services are unhealthy.
- (2026-09-15) Decision: keep T16 adapter repair separate unless governed T480
  status proves Plane healthy and the adapter failure remains reproducible.
  Rationale: this avoids coupling private service health with client transport.
- (2026-09-15) Decision: add health checks only for Plane's stateful dependency
  services, using the official test-stack probes. Rationale: this avoids
  inventing application endpoint contracts while materially improving readiness
  evidence.

## Outcomes & Retrospective

The T480 `plane_status` operation passed on 2026-09-15: 11 required services
were present and the proxy was loopback-only. Focused adapter tests passed.
The remaining gap is the previously observed T16 adapter PowerShell request
failure; it is outside Plane runtime health and needs its own bounded repair
plan before changes are made.

## Context and Orientation

`compose.yaml` includes `plane/compose.yaml` using the ignored
`plane/plane.env`; `plane/compose.yaml` declares 13 digest-pinned images and a
loopback-only proxy. `scripts/plane_adapter.py` is a T16-side read-only client.
`scripts/t480_adapter.py` and `t480/command-catalog.json` form the fixed T480
operation boundary, but neither currently has a Plane status operation.

The remediation must preserve the root Compose environment context. Validation
uses `docker compose config --quiet`, never rendered configuration. Any live
T480 invocation must use an allowlisted read-only adapter operation and produce
only redacted service/health metadata.

## Plan of Work

Milestone 1 determines stable, pinned-image health probes and their expected
responses. It ends with a documented contract rather than a speculative curl.

Milestone 2 adds Compose health checks and a fixed T480 `plane_status` action
that reports only service state, health, loopback listener class, and bounded
non-secret diagnostics. It ends with unit/config validation.

Milestone 3, after explicit approval, deploys no new images but applies the
reviewed configuration and obtains T480 evidence. It ends with either a healthy
result or a diagnosis that drives a separate repair plan.

## Concrete Steps

1. Inspect pinned Plane image documentation/source to identify stable health
   endpoints for frontend/proxy/API and dependency readiness. Reject a probe
   that needs credentials or returns sensitive content.
2. Add health checks only to services with verified endpoints, define startup
   timing, and retain the current loopback proxy publication. Validate with the
   root `docker compose config --quiet` and focused tests.
3. Add a read-only `plane_status` operation to the T480 catalog/adapter with no
   arbitrary arguments or shell mode. Its output must omit secrets, private
   addresses, logs, and workspace data.
4. Update Plane documentation and the access skill to use the root composition
   and status operation. Add tests that reject unsupported operation arguments.
5. After explicit approval, invoke the operation on T480 and capture only its
   non-secret pass/fail evidence. If Plane is healthy but T16 access still
   fails, open a separate adapter-transport plan with the observed error class.

## Validation and Acceptance

- Root Compose validation succeeds without resolved secret output.
- Tests prove the new operation is fixed and read-only, with no free-form
  command, credential, or private-address output.
- A T480 status result reports required Plane services and verified health
  criteria without changing service state.
- The T16 path is evaluated separately from T480 health; neither claim implies
  the other.
- The proxy remains loopback-only and no firewall/router change is made.

## Idempotence and Recovery

Static checks and status operations are repeatable. Compose health-check
configuration changes require approval and can be reverted by restoring the
previous tracked Compose revision; they do not remove volumes or data. Stop and
create a diagnosis plan if a health probe is unstable or needs a secret.

## Artifacts and Notes

Relevant artifacts are `plane/compose.yaml`, root `compose.yaml`, Plane docs,
the T480 catalog/adapter/tests, and this plan. Keep `plane/plane.env`, API keys,
raw logs, T480 addresses, and workspace content out of Git and the plan.
