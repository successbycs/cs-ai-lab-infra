# Use the proven Plane SSH-forward transport

This ExecPlan is a living document. Maintain it in accordance with
[`PLANS.md`](../PLANS.md). Keep `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

Status: complete

## Purpose / Big Picture

Make the shared AI Lab Plane access path use the Forex-proven Windows OpenSSH
local forward while preserving Plane's T480 loopback-only publication. A T16
operator can start the documented relay, browse the local Plane URL, and obtain
an end-to-end web-status result without adding LAN ingress, a firewall rule, or
any generic remote-command capability.

This changes only the T16-side private transport and its documentation/tests.
It does not change Plane containers, images, volumes, data, T480 firewall
policy, application-board content, or credentials.

## Progress

- [x] (2026-09-23 00:00Z) Diagnosed the user-visible browser failure: T480 Plane status passed while the T16 Python relay was not running and its approved start attempt exited without becoming available.
- [x] (2026-09-23 00:00Z) Confirmed Forex documents and records a successful strict-host-key-checked Windows OpenSSH forward for this same local Plane endpoint.
- [x] (2026-09-23 00:00Z) Implemented the fixed Windows OpenSSH-forward transport in the shared relay, retaining bounded target resolution and local-only binding.
- [x] (2026-09-23 00:00Z) Added focused tests and operator documentation while preserving the existing local URL guidance.
- [x] (2026-09-23 00:00Z) Started the user-authorized local relay and verified HTTP 200 through the adapter.

## Surprises & Discoveries

- The governed T480 `plane_status` operation passed: Plane's required services are healthy and its proxy remains loopback-only. The failure is T16 transport, not Plane service health.
- The prior Python relay suppresses its detached child process output, so its failed startup did not provide a specific failure reason.

## Decision Log

- (2026-09-23) Decision: adopt the Forex-tested fixed Windows OpenSSH forward as the T16 relay transport. Rationale: it has a recorded successful read-back for the same private destination and relies on the existing governed target resolution and strict SSH host verification.
- (2026-09-23) Decision: verify the local HTTP endpoint after process startup rather than treating a live SSH process as proof. Rationale: an SSH listener can exist while its remote connection is unavailable.

## Outcomes & Retrospective

Complete. The shared relay now starts the fixed Windows OpenSSH forward and
records only protected local process metadata. Focused Plane tests and the full
repository quality suite passed; the local Plane endpoint returned HTTP 200.
No Plane service, firewall, data, or public exposure changed.

## Context and Orientation

`scripts/plane_t16_relay.py` is the shared T16 client transport. It reads only
the protected Plane origin and the pre-existing T480 SSH target configuration.
`scripts/t480_adapter.py execute --operation plane_status` is the only accepted
T480 health/proxy discovery path. The local origin is `http://127.0.0.1:18090`;
the remote Plane proxy is discovered through the governed status operation.

Forex's `docs/plane-integration.md` documents a Windows `ssh.exe -N -T -L`
forward to the same loopback endpoint, using batch mode and strict host-key
checking. Its recorded implementation evidence states that the local forward
returned HTTP 200. The shared implementation must use the same constraints but
must not duplicate a credential or write a generic tunnel facility.

## Plan of Work

Replace the relay's per-connection remote bridge with one fixed local SSH
forward process. It resolves the fixed target using the existing transport
configuration, requests the Plane proxy port from the existing status operation,
and starts `ssh.exe` through the Windows PowerShell boundary using exactly the
existing batch-mode, strict-host-key, timeout, and connection-attempt settings.
It binds only the configured loopback origin.

The start operation records only a local process ID and non-secret transport
kind. It waits for both process survival and an HTTP-200 check through
`plane_adapter.web_status`; failure terminates the child and leaves no stale
state. Stop terminates only that local child. Tests prove fixed arguments,
target validation, state shape, failed web verification cleanup, and no
listener broadening.

## Concrete Steps

1. Update `scripts/plane_t16_relay.py` to construct the fixed Windows SSH
   forward from the shared target resolver and discovered proxy port. No caller
   can provide an address, port, target, or remote command.
2. Record a minimal local state file with mode 0600 and use process liveness
   only for status; call the bounded Plane web-status operation for end-to-end
   verification during start.
3. Extend `tests/test_plane_t16_relay.py` for the fixed forwarding contract and
   failed-start cleanup. Preserve unrelated current worktree edits.
4. Update `docs/plane-access.md` and `plane/RUNBOOK.md` with the transport
   description, keeping the existing local URL and no-public-ingress boundary.
5. Run focused tests, the ExecPlan structure check, and the approved start plus
   web-status check. Do not start, stop, or change Plane services on T480.

## Validation and Acceptance

| Requirement / risk | Evidence | Passing observation |
| --- | --- | --- |
| No broader exposure | Source/test inspection | Forward bind is exactly T16 loopback; no firewall or public address appears. |
| SSH safety | Focused unit test | Command uses only the resolved target, `BatchMode=yes`, and `StrictHostKeyChecking=yes`. |
| T480 health prior to transport | Governed `plane_status` | Required services healthy and proxy loopback-only. |
| User-visible path | `plane_adapter.py web-status` after approved start | The configured local Plane origin returns HTTP 200. |
| Failure recovery | Focused failure-path test | Failed verification removes state and terminates the spawned local forward. |
| Repository integrity | Focused tests and `make execplan-check` | Tests and structure validator pass without secrets in tracked output. |

## Idempotence and Recovery

Starting when a verified forward is already live is a no-op. A failed startup
cleans up only its own child process and state file. Stopping targets only the
PID recorded in the protected local state; it never signals a T480 process. If
the web endpoint fails after a start, stop the local forward and investigate
the existing private transport configuration; do not add a firewall exception,
port proxy, or broader listener as a workaround.

## Artifacts and Notes

Tracked artifacts are this plan, the relay implementation, its focused tests,
and Plane operator docs. The ignored local state file may hold only process and
transport metadata and is mode 0600. Credentials, target addresses, raw SSH
output, and Plane board/data are excluded from artifacts and handoff.
