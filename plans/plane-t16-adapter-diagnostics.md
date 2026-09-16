# Diagnose the T16 Plane adapter transport

This ExecPlan is a living document. Maintain it in accordance with
[`PLANS.md`](../PLANS.md).

Status: complete

## Purpose / Big Picture

Make the bounded T16 Plane adapter report a safe, actionable failure class or
success for the configured private Plane origin, without exposing its token or
changing Plane/network state.

## Progress

- [x] (2026-09-15 00:00Z) Created the diagnostic plan after a generic Windows
  PowerShell request failure.
- [x] (2026-09-15 00:00Z) Added redacted PowerShell failure classification and
  focused tests.
- [x] (2026-09-15 00:00Z) Implemented the approved loopback-only T16 relay and
  re-ran the bounded web status successfully.

## Surprises & Discoveries

- The current adapter discards PowerShell stderr and maps every nonzero result
  to one generic error, preventing safe diagnosis.
- Plane's proxy is loopback-bound inside the T480 WSL distribution. A normal
  SSH local forward terminates its destination at T480 Windows, not that WSL
  loopback, so it cannot provide browser access by itself.

## Decision Log

- (2026-09-15) Decision: expose only a bounded failure class and exit code, not
  PowerShell stderr, request URLs, tokens, or raw responses.
- (2026-09-15) Decision: use a fixed per-connection byte relay over the
  existing strict-host-key-checked SSH transport. Rationale: it preserves both
  T16 and T480 loopback-only access without adding ingress or firewall rules.

## Outcomes & Retrospective

Complete. `web-status` returns HTTP 200 through the local relay. The separate
`list-projects` request currently reports only a redacted transport failure;
that concerns the local API-token/client path, not Plane web availability.

## Context and Orientation

`scripts/plane_adapter.py` invokes `powershell.exe` for private T16 requests.
The T480 Plane status passed, so this work is limited to the T16 adapter.

## Plan of Work

Add deterministic error classification, test it with mocked subprocess results,
then run the adapter's existing read-only `web-status` operation.

## Concrete Steps

1. Preserve the fixed access boundary and token handling.
2. Map timeout, unavailable PowerShell, and nonzero request failures to safe
   diagnostic classes; do not include raw process output.
3. Add the explicit-approval local relay, constrained to T16 loopback and the
   T480 governed Plane proxy status.
4. Add focused tests and run `web-status` again.

## Validation and Acceptance

- Tests prove stderr/token text cannot enter adapter output and the relay uses
  strict host-key checking with no generic forward.
- `web-status` returns HTTP 200 from the configured local origin.
- No Plane mutation, credential change, public ingress, or firewall change
  occurs.

## Idempotence and Recovery

The relay can be stopped with `python3 scripts/plane_t16_relay.py stop
--approve`; it affects only its T16 loopback listener. Revert only the adapter
and relay code if the fixed boundary needs to be withdrawn.

## Artifacts and Notes

Relevant files are `scripts/plane_adapter.py`, `tests/test_plane_adapter.py`,
and this plan. No secrets or raw PowerShell output are tracked.
