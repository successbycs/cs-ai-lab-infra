# Publish Ollama's raw API to the trusted private LAN

This ExecPlan is a living document. Maintain it in accordance with
[`PLANS.md`](../PLANS.md). Keep `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

Status: blocked

## Purpose / Big Picture

Make the optional T480 Ollama service available to every service and device on
the trusted private LAN at `http://<T480-private-address>:11434`. LAN consumers
can use this as their Ollama-compatible base URL for inference and embeddings.

This is an intentional MVP trade-off: the endpoint has no TLS or client
authentication. Any device on the permitted LAN can submit prompts, consume
compute, and use installed models. It must never be port-forwarded, published
through public DNS, exposed by a tunnel, or made available to the internet.
PostgreSQL, n8n, Docker, SSH, MCP, and other services retain their policies.

## Progress

- [x] (2026-09-26 04:45Z) Reviewed the Ollama Compose profile, network policy,
  T480 operation catalog, and dashboard LAN pattern.
- [x] (2026-09-26 04:45Z) Revised the design to the owner-selected
  unauthenticated private-LAN MVP rather than an HTTPS gateway.
- [x] (2026-09-26 05:00Z) Added the fixed Compose bind, firewall operations,
  policy/docs, and regression tests without applying them to the T480.
- [x] (2026-09-26 05:00Z) Passed focused Ollama regression tests and local
  adapter/catalog syntax checks. Resolved Compose validation is blocked on the
  T16's unavailable Docker Desktop WSL integration.
- [x] (2026-09-26 05:05Z) Passed 129 repository tests with the one
  WSL-dependent boot-launcher test deselected; `make quality` exercises the
  same test and remains blocked by the local WSL socket failure.
- [x] (2026-09-26 05:17Z) Committed and pushed the scoped implementation as
  `2360218` (`Expose Ollama on trusted private LAN`).
- [ ] (blocked 2026-09-26 05:17Z) Deploy the pushed revision and execute the
  approved Ollama bind/firewall rollout after the T16 Windows/WSL bridge works.
- [ ] (authorized rollout) Apply and verify the one scoped private-LAN exposure
  change on the T480.

## Surprises & Discoveries

- The current `ollama` Compose service has no published host port and is only
  available to the internal Docker network as `http://ollama:11434`.
- The current exposure policy says that Ollama has no published port, so policy
  and T480 operation-catalog changes precede any rollout.
- The dashboard has a fixed Private-profile firewall/proxy pattern that can
  inform an Ollama-specific operation, but its port and API are different.
- The local T16 WSL environment reports that `docker` is unavailable because
  Docker Desktop WSL integration is not active. This blocks only local resolved
  Compose validation; no conclusion about the T480 Compose runtime follows.
- `make quality` has one unrelated environment-blocked test: the existing
  PowerShell boot-launcher quoting test invokes WSL and receives the same
  `UtilBindVsockAnyPort` socket failure. The remaining 129 tests pass when it
  is deselected.
- The governed `repository_status` deployment preflight and a direct local
  `wsl.exe --status` check both fail immediately with
  `UtilBindVsockAnyPort:307: socket failed 1`. The failure occurs on the T16
  before an SSH session reaches the T480, so no checkout, service, firewall,
  or model state has changed.

## Decision Log

- (2026-09-26) Decision: publish raw HTTP on TCP 11434 to the trusted private
  LAN without TLS or authentication for the MVP. Rationale: the owner accepts
  the reduced security in exchange for simple network-wide access.
- (2026-09-26) Decision: retain a Private-profile-only Windows firewall rule
  and prohibit router forwarding/public ingress. Rationale: this minimum
  boundary keeps an unauthenticated model API off the internet.
- (2026-09-26) Decision: keep Ollama optional and preserve its named model
  volume. Rationale: LAN publication must not make it a required lab dependency
  or discard models on rollback.

## Outcomes & Retrospective

The repository implementation is complete: Ollama is loopback-only by default,
with fixed enable/disable and Private-profile/local-subnet firewall operations.
No T480 port, firewall rule, proxy, model, or service changed. The reviewed
implementation is pushed as `2360218`, but deployment is blocked by the T16
Windows/WSL bridge before it reaches the T480. Restore local WSL operation,
then rerun the governed `repository_status`, approval-gated `repository_update`,
`ollama_lan_enable`, `ollama_lan_firewall_enable`, and `ollama_lan_verify`
sequence. Resolved Compose validation must run from a Docker-capable environment
before rollout. The full-quality gate also needs the local WSL socket failure
resolved or an equivalent healthy Windows/WSL validation environment.

## Context and Orientation

The T480 is the private persistent runtime. Its `ollama` Compose service is
optional, joins the internal Docker bridge, stores models in `ollama_models`,
and now has a loopback-default configurable `ports` entry. Docker consumers
use `http://ollama:11434`; that name is not reachable from the LAN.

Desired Compose publication is not proof of network access. Windows firewall
profile/scope, WSL/Docker forwarding, and router configuration affect the
effective path. The fixed T480 adapter must gain read-only status plus
approval-gated enable/disable/verify operations; no generic firewall or remote
shell parameter is permitted.

## Plan of Work

### Milestone 1 — Change the documented exposure policy

Update `docs/network-exposure.md`, `docs/architecture.md`, `README.md`,
`ollama/README.md`, and `docs/decisions.md` to describe the MVP contract:
unauthenticated TCP 11434 is available only on the T480 Windows Private network
profile. Use URL/address placeholders in Git.

State that all permitted LAN devices can invoke the model API. Exclude
credentials, sensitive/customer prompts, phones, public networks, router port
forwards, public DNS, and tunnels until a separate authenticated-access design
is approved.

Expected result: operators understand the URL and the intentional risk. Proof:
docs/link checks and one exposure table state the same port, audience, and
rollback.

### Milestone 2 — Add a fixed, reversible publication path

Add an Ollama Compose port mapping controlled by `OLLAMA_BIND_ADDRESS` and
`OLLAMA_PORT`, defaulting to loopback in examples so a fresh deployment does
not expose the API. The approved LAN rollout sets the reviewed bind and fixes
the port at `11434`.

Add fixed catalogued operations:

1. `ollama_lan_status` — read-only named firewall-rule and listener status.
2. `ollama_lan_enable` / `ollama_lan_disable` — approval-gated; change only
   the fixed Compose bind and start/verify only Ollama. Both preserve models
   and restore the protected local `.env` if configuration or startup fails.
3. `ollama_lan_firewall_enable` / `ollama_lan_firewall_disable` —
   approval-gated; add or remove only the named Private-profile local-subnet
   inbound TCP 11434 rule.
4. `ollama_lan_verify` — read-only local API, listener, and firewall-policy
   verification.

If the approved live proof shows WSL/Docker presents loopback-only access to
Windows, stop and add a separate fixed Windows-forwarding operation like the
dashboard's. Do not add a generic proxy or caller-provided bind/port as a
workaround.

Expected result: access is named, limited, approval-gated, and reversible.
Proof: catalog/adapter tests prove fixed port/profile behavior and reject
arbitrary address, port, firewall, shell, or proxy arguments.

### Milestone 3 — Validate locally and document consumers

Add a provider-configuration example using
`http://<T480-private-address>:11434`, configurable model name, timeouts, and
fallback provider. Do not hard-code a real address. State that consumers need
no credentials and should use this endpoint only for low-risk MVP workloads.

Run configuration validation, adapter-contract tests, and synthetic client
tests. Confirm Docker consumers still use `http://ollama:11434` unchanged.
Run `make quality` and `docker compose config --quiet`.

Expected result: a consumer knows the private URL and internal consumers retain
access. Proof: local synthetic/config tests and Compose validation pass without
secrets or real addresses.

### Milestone 4 — Make one approved live change and retain evidence

After explicit approval of the Compose publication, firewall rule, optional
forwarding path, and rollback: collect redacted before state; start/verify
Ollama only if separately approved; deploy the reviewed configuration; enable
the firewall rule; and collect matching after state.

From an approved LAN client, send one synthetic HTTP request and check a
response. Confirm a non-Private/public path does not reach it and that no
router port-forward/public ingress exists. Retain only pass/fail/interface
observations—not addresses, prompts, outputs, or firewall dumps. Measure T480
memory, CPU, and physical disk headroom under the test.

Expected result: an approved LAN client reaches raw Ollama HTTP; no broader
claim is made. Proof: governed status/verify and before/after reachability
evidence establish the point-in-time state.

## Concrete Steps

1. Update policy, architecture, operator, and Ollama docs for the deliberate
   unauthenticated LAN API; add the decision record.
2. Update Compose and `.env.example` with the fixed bind/port contract while
   preserving the profile, health check, internal network, digest pin, and
   named model volume.
3. Add `ollama_lan_*` operations to `scripts/t480_adapter.py` and
   `t480/command-catalog.json`; update the T480 README and operation tests.
4. Add tests for loopback defaults, fixed port 11434, Private-only scope,
   disabled/public-path rejection, disable cleanup, and unchanged PostgreSQL/
   n8n bindings.
5. Run focused tests, `docker compose config --quiet`, `make quality`, and
   exposure-policy review. Do not run adapters, change firewall, start a
   service, or publish a port during local implementation.
6. Request precise live-change approval, then do Milestone 4. If verification
   fails, use fixed disable and return to Docker-internal-only access.

## Validation and Acceptance

| Requirement or risk | Evidence |
| --- | --- |
| Raw Ollama reaches the private LAN | An approved LAN client makes one synthetic HTTP request to TCP 11434 and receives the expected bounded response. |
| No accidental broad publication | Firewall/forwarding is Private-profile-only; non-Private/public-path checks fail; no router port-forward/public DNS/tunnel exists. |
| Configuration matches policy | Resolved Compose publishes only the fixed Ollama port as designed; PostgreSQL/n8n stay loopback-only. |
| No arbitrary remote control | Catalog and tests show fixed port/rule/profile operations and reject arbitrary parameters. |
| Minimum runtime safety | Ollama health/capacity are checked; synthetic request needs no model pull, volume deletion, or unapproved restart. |
| Recovery is safe | Disable removes only Ollama LAN publication/firewall/forwarding and preserves models/unrelated services. |

Local tests do not prove Windows firewall, WSL forwarding, router state, or LAN
reachability. Those need the separately approved live evidence procedure.

## Idempotence and Recovery

Status, configuration validation, and synthetic local tests are repeatable.
Enable must refuse unexpected existing rules/listeners and may be rerun only
after status shows the expected state. If verification fails or the owner
withdraws the LAN-access decision, fixed disable removes only the Ollama path.
Never delete `ollama_models`, backups, or unrelated firewall rules on rollback.

## Artifacts and Notes

- Existing sources: `compose.yaml`, `.env.example`, `ollama/README.md`,
  `docs/network-exposure.md`, `docs/architecture.md`, `README.md`,
  `scripts/t480_adapter.py`, `t480/command-catalog.json`, and adapter tests.
- Proposed implementation: policy/docs, configurable Ollama publication, fixed
  adapter operations, and tests.
- Keep actual addresses, raw firewall/socket output, prompts, model output,
  and local execution evidence out of Git.
