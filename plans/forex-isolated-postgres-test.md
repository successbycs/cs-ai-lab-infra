# Forex isolated PostgreSQL verification operation

This ExecPlan is a living document. Maintain it in accordance with
[`PLANS.md`](../PLANS.md). Keep `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

Status: active

## Purpose / Big Picture

Provide one approval-required, fixed T480 operation that runs the two Forex
PostgreSQL reservation tests against a disposable loopback-only PostgreSQL
container. The observable outcome is a redacted pass/fail result and no
remaining test container. It never connects to the shared lab PostgreSQL
service, MT5, or a broker.

## Progress

- [x] (2026-09-29 11:18Z) Confirmed the approved T480 adapter reaches Docker;
  Docker Engine and Compose are available.
- [x] (2026-09-29 11:18Z) Confirmed no existing allowlisted operation can run
  this isolated Forex test; no ad-hoc remote command was used.
- [ ] (2026-09-29 11:18Z) Add the fixed adapter operation, catalogue entry,
  documentation, and focused contract tests.
- [ ] (2026-09-29 11:18Z) Obtain explicit approval to execute the new
  state-changing operation after it is committed and deployed to T480.

## Surprises & Discoveries

- The local T16 WSL checkout has no PostgreSQL client, server, Docker command,
  or `FOREX_W1_TEST_DSN`. T480 Docker is healthy, but its shared adapter does
  not currently expose this disposable-test operation.

## Decision Log

- (2026-09-29) Decision: add a fixed, approval-required operation rather than
  use a generic T480 shell. Rationale: it preserves the shared adapter's
  allowlist and proves the test cannot target the trading or shared database.

## Outcomes & Retrospective

Active. The next safe step is implementation and local adapter-contract
verification. The Forex repair and its test must also be committed and present
in the fixed T480 Forex checkout. A committed shared-adapter revision and
explicit operation approval remain prerequisites to the live container run.

## Context and Orientation

`scripts/t480_adapter.py` is the only shared T480 control path. Its operation
dictionary is mirrored by `t480/command-catalog.json`, documented in
`t480/README.md`, and exercised by adapter tests. Forex's test module accepts
only a localhost nonstandard-port DSN naming `forex_w1_test`, resets only its
own `forex` schema, and is engineering proof rather than broker evidence.

The new operation will run on T480's Ubuntu WSL host from its fixed Forex
checkout. It will start one disposable PostgreSQL container on a loopback-only
ephemeral host port, wait for readiness, invoke precisely two test selectors
with a locally scoped environment variable, return a redacted summary, and
remove the named container in a shell trap. No persistent volume, network,
image build, checkout update, service restart, or listener action is allowed.

## Plan of Work

First add a narrowly encoded operation that cannot accept caller-supplied
commands, database connection strings, ports, image names, or test selectors.
Then add catalogue/README visibility and tests proving its approval gate and
isolation clauses. Finally, after both the Forex repair and shared adapter are
committed and the T480 Forex checkout contains the repair, run it once through
the adapter with explicit approval and inspect the cleanup/result evidence.

## Concrete Steps

1. Add `forex_isolated_postgres_tests` to the fixed adapter dictionary with
   `approval_required=True`. Its WSL script must require the fixed Forex
   checkout, use a random container name, bind PostgreSQL to `127.0.0.1` on an
   ephemeral port, create only database `forex_w1_test`, and clean the named
   container in `trap`.
2. Execute only the two reservation test selectors with the generated DSN;
   return the test exit status after cleanup. Never print the DSN or password.
3. Add the matching catalogue and README entries, then focused contract tests.
4. Run focused tests and `make quality`. Do not run the new T480 operation
   until the shared adapter revision is committed, deployed, and explicitly
   approved.

## Validation and Acceptance

- Static: adapter operation is fixed and approval-required; catalogue matches.
- Boundary: source asserts loopback binding, generated password, no volume,
  no shared PostgreSQL service name, no MT5/listener reference, and `trap`
  cleanup.
- Live after approval: both Forex selectors pass and final inspection reports
  no temporary container. A failure still removes the container and does not
  alter shared services.

## Idempotence and Recovery

Each invocation uses a fresh container name and removes it in an EXIT trap.
If Docker cannot start or readiness times out, the command fails closed and
the trap removes only that invocation's container. No volume or shared
database is created, modified, or deleted. Repeating an invocation is safe;
do not retry after an ambiguous adapter transport failure without inspecting
the governed result.

## Artifacts and Notes

Tracked files: this plan, `scripts/t480_adapter.py`,
`t480/command-catalog.json`, `t480/README.md`, and focused adapter tests.
Local adapter audit metadata remains ignored. Do not commit private host
output, DSNs, passwords, or generated runtime evidence.
