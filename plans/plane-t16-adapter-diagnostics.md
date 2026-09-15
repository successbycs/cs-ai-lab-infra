# Diagnose the T16 Plane adapter transport

This ExecPlan is a living document. Maintain it in accordance with
[`PLANS.md`](../PLANS.md).

Status: active

## Purpose / Big Picture

Make the bounded T16 Plane adapter report a safe, actionable failure class or
success for the configured private Plane origin, without exposing its token or
changing Plane/network state.

## Progress

- [x] (2026-09-15 00:00Z) Created the diagnostic plan after a generic Windows
  PowerShell request failure.
- [ ] (2026-09-15 00:00Z) Add redacted PowerShell failure classification and
  focused tests, then re-run read-only status.

## Surprises & Discoveries

- The current adapter discards PowerShell stderr and maps every nonzero result
  to one generic error, preventing safe diagnosis.

## Decision Log

- (2026-09-15) Decision: expose only a bounded failure class and exit code, not
  PowerShell stderr, request URLs, tokens, or raw responses.

## Outcomes & Retrospective

Active. Next safe step: add the bounded diagnostic result and test it.

## Context and Orientation

`scripts/plane_adapter.py` invokes `powershell.exe` for private T16 requests.
The T480 Plane status passed, so this work is limited to the T16 adapter.

## Plan of Work

Add deterministic error classification, test it with mocked subprocess results,
then run the adapter's existing read-only `web-status` operation.

## Concrete Steps

1. Preserve the current fixed operation set and token handling.
2. Map timeout, unavailable PowerShell, and nonzero request failures to safe
   diagnostic classes; do not include raw process output.
3. Add focused tests and run `web-status` again.

## Validation and Acceptance

- Tests prove stderr/token text cannot enter adapter output.
- A failed read-only request reports a useful safe class.
- No Plane mutation, credential change, or network change occurs.

## Idempotence and Recovery

All diagnostics are read-only and repeatable. Revert only the adapter code if
the new classification changes its fixed operation boundary.

## Artifacts and Notes

Relevant files are `scripts/plane_adapter.py`, `tests/test_plane_adapter.py`,
and this plan. No secrets or raw PowerShell output are tracked.
