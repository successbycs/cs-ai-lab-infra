# Repository improvement waves

This plan implements the findings in [the repository deep dive](repo-deep-dive.md) without replacing the existing M0–M10 evidence system. Estimates assume one maintainer who can review local changes promptly and schedule T480 work separately. They are effort ranges, not calendar promises.

## Roadmap

| Wave | Outcome | Findings | Dependencies | Effort | Change risk | Exit gate |
| --- | --- | --- | --- | --- | --- | --- |
| Wave 0 — Truthful configuration and evidence | One consistent exposure policy and a verifier that recognizes the reviewed current image while preserving historical proof. | F-001, F-002 | None | 1–2 days | Medium: evidence semantics | Current and historical verifier fixtures pass; docs have one policy. |
| Wave 1 — Recoverable data and schema evolution | A defined, testable recovery inventory plus recorded, repeatable database migration state. | F-003, F-005 | Wave 0 | 3–5 days plus scheduled drill | High: persistent data | Clean synthetic full-stack recovery and migration-path proof pass. |
| Wave 2 — Honest monitoring states | Monitoring clearly separates observation, redacted publication, server availability, and stale data. | F-004, F-008 | Wave 0; Wave 1 recovery preflight for any live change | 2–4 days | Medium | Unit/contract tests pass; any live dashboard change has LAN and freshness evidence. |
| Wave 3 — Bounded ownership and reproducible delivery | The adapter's compatibility surface has an explicit migration path and every local check runs from a declared dev environment and CI. | F-006, F-007 | Wave 0 | 3–5 days | Medium | One ownership transfer is proven or explicitly deferred; CI and local quality command pass. |
| Wave 4 — Tailnet policy readiness | A reviewable, offline-tested least-privilege policy template is ready before M10. | F-009 | Wave 0; no M10 live action | 0.5–1 day | Low | Template tests pass and contains no real device identity or apply step. |

Wave 0 is first because source-of-truth errors undermine every later preflight, evidence bundle, and operator decision. Wave 1 precedes live monitoring changes because a monitoring deployment should have a recovery contract. Waves 3 and 4 can proceed after Wave 0, but should not run concurrently against the same adapter and documentation files. Wave 2 may be implemented locally before Wave 1 is fully complete, but its live deployment gate requires Wave 1's recovery preflight.

## Wave 0 — Truthful configuration and evidence

**Objective and value.** Make an operator see the same PostgreSQL and dashboard policy in the README, architecture, setup guide, environment template, health checks, and evidence verifier. Before: an operator receives contradictory LAN/loopback instructions and a current M2 evidence bundle cannot pass its verifier. After: desired policy, effective-state validation, and verifier expectations are explicit and testable.

**Scope.** Address F-001 and F-002 in `README.md`, `docs/architecture.md`, `docs/setup.md`, `docs/operations.md`, `postgres/README.md`, `.env.example`, `compose.yaml` only if configuration is intentionally changed, `scripts/verify-m2-evidence.sh`, M6 text, and new tests/fixtures. Preserve historical M2 evidence-verification capability. Exclude T480 firewall changes, port binding changes, image upgrades, and database changes.

**Preserved strengths.** S-001, S-002, S-003, S-004, and S-006. Keep PostgreSQL/n8n loopback defaults, the explicit dashboard LAN design, digest pinning, and approval gates.

**Prerequisites.** Read current Compose and actual adapter behavior. No remote access needed for repository changes. A live effective-binding check is a later separately approved validation, not an implementation prerequisite.

| Task | Change approach | Effort / PR boundary |
| --- | --- | --- |
| W0-T1 | Write one exposure matrix defining desired Compose bind, intended audiences, host-firewall dependency, and evidence that proves effective reachability. Remove the tracked private address and stale direct-client instructions. | Small documentation PR. |
| W0-T2 | Classify `docker compose port` as desired container-publish state, not proof of firewall/public exposure. Make health-check output and docs say what each check proves. | Same PR as W0-T1. |
| W0-T3 | Replace the hard-coded current-image assertion in `verify-m2-evidence.sh` with a versioned manifest contract or verifier parameter derived from a reviewed fixture. Retain a historical verifier/fixture for existing 1.118.1 bundles. | Separate evidence-integrity PR. |
| W0-T4 | Add tests that fail when the current Compose n8n image and current verifier fixture disagree; test historical fixture compatibility. Reconcile M6 wording only after W0-T3 passes. | Same PR as W0-T3. |

**Acceptance criteria.**

- No tracked private IP address or machine-specific connection URI remains in documentation.
- The exposure matrix has a single baseline: PostgreSQL and n8n loopback-only; dashboard access is explicitly conditional on its bind and host Private-profile policy.
- A fixture representing the checked-in Compose n8n image passes the current M2 verifier; a retained historical fixture passes its historical verifier or has an explicit immutable archive policy.
- A test fails if a future Compose n8n image changes without updating the reviewed current evidence contract.
- The M6 `validation_integrity_corrected` acceptance check is only recorded after code, tests, and appropriate T480 evidence support it.

**Validation.** Run `python3 -m pytest -q`, `bash -n scripts/*.sh`, `python3 -m compileall -q scripts t480_core monitoring tests`, JSON parsing, and a verifier-fixture test that never reads real evidence. On the T480, after explicit operator approval for read-only inspection, collect redacted proof that PostgreSQL/n8n are loopback-only and dashboard access has the intended Private-LAN result from the T16. Record pass/fail and interface class only, never an address or credentials.

**Release and recovery.** Documentation and verifier changes should ship before any new M2 capture. Do not overwrite old raw evidence; preserve its original verifier and manifest interpretation. Roll back a faulty new verifier by reverting only the new verifier/fixture contract, then use the retained historical verifier for old bundles. A live bind change requires a pre-change repository backup and a clearly documented reversion of the exact binding/firewall rule; it is outside this wave.

**Operational authorization.** Local changes and fixture tests are ordinary repository work. Any `t480_adapter.py` inspection, firewall-status operation, or LAN reachability test remains subject to the repository's existing remote-operation process; no mutation is authorized by this wave.

**Exit gate.** The source tree has one exposure policy, both verifier fixtures pass, local validation passes, and no later wave relies on an ambiguous image or exposure claim. Pause and replan if historical evidence cannot be retained or if a live test contradicts the desired policy.

## Wave 1 — Recoverable data and schema evolution

**Objective and value.** Turn “PostgreSQL backup plus synthetic restore” into a precise full-lab recovery contract, and make database state identifiable across new, upgraded, and restored environments. Before: the exact recoverable set is inferred. After: a maintainer can inventory, protect, restore, and prove all required state without treating the lab database as a test target.

**Scope.** Address F-003 and F-005 through recovery-design documents, backup manifest/tooling, a protected method for the n8n encryption key, volume/file recovery strategy, a migration ledger/checksum mechanism, adapter changes, and synthetic integration tests. Include PostgreSQL, n8n database/files, configuration, encryption-key recovery, and optional Ollama-model disposition. Exclude customer data, production cloud backups, automatic deletion/retention enforcement, and restoration of the current live lab as a test.

**Preserved strengths.** S-001, S-002, S-003, S-004, and S-005. Keep secrets outside Git, raw evidence local, PostgreSQL as a separate service, and the isolated M3 drill.

**Prerequisites.** Wave 0 must establish the policy baseline. The owner must decide the protected off-host destination, encryption/physical-access model, recovery-point objective, retention duration, and whether model artifacts are recoverable or re-downloadable. Do not put that destination or its credentials in Git.

| Task | Change approach | Effort / PR boundary |
| --- | --- | --- |
| W1-T1 | Write a recovery inventory and RPO/RTO assumptions: database dump, Compose revision, `.env` recovery mechanism, n8n files/data, raw evidence policy, dashboard output, and optional models. Mark each required, reconstructable, or intentionally excluded. | Design/document PR. |
| W1-T2 | Add a backup manifest and integrity verification that identifies artifacts, timestamps, hashes, source revision, and recovery scope without embedding secrets. Add an approved external-copy interface only after destination design is chosen. | Backup-tooling PR. |
| W1-T3 | Introduce a minimal migration ledger with filename/checksum/applied timestamp; make migration application transaction-aware where possible and refuse checksum drift. Add fresh, upgrade, rerun, and controlled-failure tests. | Database migration PR. |
| W1-T4 | Build a clean, synthetic full-stack recovery drill. It must restore into isolated names/volumes and use a test-only encryption-key path; it must never target the active n8n database or read customer content. | Recovery-drill PR. |
| W1-T5 | Perform a separately approved T480 drill and capture a raw, independently verified evidence bundle. Update milestone wording to state exactly what this proof covers. | Live evidence task, separate from code PRs. |

**Acceptance criteria.**

- The recovery inventory states exactly what a PostgreSQL dump can and cannot restore.
- Backup output has a non-secret manifest and integrity check; lack of any required artifact fails preflight clearly.
- Fresh database initialization, an upgrade from prior monitoring migrations, and a re-run of the same migration produce an expected ledger state; altered prior migration content is rejected.
- A clean synthetic restore proves n8n can start with restored test state and its preserved encryption key, while no live database, volume, or secret is modified.
- The T480 evidence bundle proves the selected recovery scope, verifier result, and off-host copy confirmation without exposing paths, credentials, or data.

**Validation.** Add unit tests for manifests and migration ledger behavior; use disposable PostgreSQL only if a local test container can be started safely. Run the Wave 0 suite. The proposed live drill requires explicit approval, a fresh backup, capacity preflight, a known recovery target, and post-drill cleanup only through a separately reviewed action. Evidence must include integrity results and a synthetic end-to-end n8n health result.

**Release and recovery.** Release design/docs first, then backup manifest, then migration ledger, then the recovery drill. Back up before applying the ledger to any existing T480 database. Make ledger rollout forward-compatible: preserve existing schema and provide a read-only inventory mode. If a migration fails, stop, retain the error/evidence locally, restore from the known good backup or use a reviewed forward fix; do not mark it applied manually. Do not use Git revert as database recovery.

**Operational authorization.** Local implementation and disposable tests are in scope. Creating off-host copies, accessing `.env`, applying migrations, creating volumes/databases, and the T480 drill need the repository's existing explicit approval and evidence procedure.

**Exit gate.** The inventory is agreed, local recovery/migration tests pass, and the synthetic live drill is independently verified. Pause if the owner has not chosen a recoverable secret/off-host-copy method or if the drill exposes unanticipated persistent state.

## Wave 2 — Honest monitoring states

**Objective and value.** Make status data explain whether the server is alive, when the T480 was last observed, and whether redacted monitoring output was deliberately persisted. Before: an HTTP 200 can coexist with absent or stale health data. After: an operator can distinguish those states without accessing raw logs.

**Scope.** Address F-004 and the evidence-driven portion of F-008 in the T480 operation contract, `scripts/t480_adapter.py`, `monitoring/`, dashboard renderer/server, health-check script, migration files, tests, and operations docs. Exclude automatic remediation, notifications, scheduler activation, image replacement, resource limits, and firewall changes.

**Preserved strengths.** S-002, S-003, S-004, S-005, and S-006. Keep the dashboard static, status-only, redacted, and non-controlling; keep recovery approval-gated.

**Prerequisites.** Wave 0. Define a freshness threshold and whether a failed control-path check should be published only locally or also remotely when access returns. Any database migration/live dashboard deployment requires the Wave 1 recovery preflight.

| Task | Change approach | Effort / PR boundary |
| --- | --- | --- |
| W2-T1 | Define observation, publication, local-history, server-availability, and data-freshness semantics in the contract and audit schema. | Documentation plus contract PR. |
| W2-T2 | Add a bounded freshness calculation and visible `fresh`, `stale`, or `no-data` dashboard state. Keep `/healthz` scoped to server liveness; add a separate data-readiness/freshness endpoint if needed. | Monitoring implementation PR. |
| W2-T3 | Add tests for no data, stale data, failed publication, malformed payload, and status escaping. Ensure `Healthcheck` result names each persistence side effect. | Same PR as W2-T2. |
| W2-T4 | Measure baseline and peak T480 CPU/RAM/disk use through fixed read-only diagnostics. Decide from evidence whether F-008 needs resource limits or a dashboard-runtime split. | Separate measurement/evidence task. |

**Acceptance criteria.**

- The command contract calls out PostgreSQL/local-history/dashboard writes as redacted data side effects and separately guarantees no service start, restart, update, exposure, or remediation.
- The dashboard visibly labels no data and stale data; server liveness is never presented as current lab health.
- A test proves stale data remains safe and distinguishable, and a test proves redaction/escaping remains intact.
- Scheduler configuration stays disabled unless a separate approval explicitly activates it. No notification destination is introduced.
- Resource limits or runtime changes are proposed only if W2-T4 evidence shows a concrete constraint.

**Validation.** Run the declared local suite plus renderer and server endpoint tests. Proposed live validation: after approved migration/deployment, publish a synthetic redacted check, observe the dashboard from the T16, wait past the defined threshold without running a new check, and capture the stale state. Verify no n8n/PostgreSQL service start/restart occurred. Do not enable a periodic scheduler for this proof.

**Release and recovery.** Deploy schema changes before code that writes new fields; maintain a reader fallback for old rows until the new dashboard has proven healthy. Back up before migration. If rendering fails, retain the prior static page and revert the dashboard code while preserving newly written redacted rows; a forward-compatible migration is preferable to a destructive rollback.

**Operational authorization.** Repository work is ordinary. The approved PostgreSQL migration adapter, dashboard service start, firewall checks, or LAN test each remain separately gated. This wave never authorizes scheduler activation.

**Exit gate.** Tests prove the state model, and a separately approved T480/T16 drill proves freshness visibility and redaction. Pause if the freshness policy cannot be agreed or if visibility requires broader network exposure.

## Wave 3 — Bounded ownership and reproducible delivery

**Objective and value.** Reduce the risk that platform maintenance is blocked by legacy application operations, while making the supported local check repeatable in a fresh environment and CI. Before: ownership transfer is open-ended and the test tool is implicit. After: compatibility has an explicit lifecycle and contributors can run one declared quality command.

**Scope.** Address F-006 and F-007 in `t480_core`, the main adapter/catalog, migration documentation, package metadata, test tooling, and a CI workflow selected by the owner. Transfer at most one operation family in this wave. Exclude deletion of unproven compatibility operations, consumer-repository changes without their owners, and live deployment.

**Preserved strengths.** S-001, S-003, S-004, and S-006. Preserve fixed operations, catalog/code agreement, strict transport behavior, audit logging, and real-machine proof requirements.

**Prerequisites.** Wave 0. Confirm an application owner and target repository for the first operation family. Choose a supported Python version range and CI provider. The documented current migration safety rule remains binding.

| Task | Change approach | Effort / PR boundary |
| --- | --- | --- |
| W3-T1 | Create an ownership/deprecation register covering each non-platform operation family, consumer, proof required, rollback location, and no-earlier-than removal condition. | Documentation PR. |
| W3-T2 | Choose one small read-only operation family and extract it to its application-owned catalog/CLI using `t480_core`; add producer and consumer contract tests. | Cross-repository compatibility PRs. |
| W3-T3 | Declare a dev/test dependency group or lockable environment, a `make`/script quality entry point, and minimum Python support. | Tooling PR. |
| W3-T4 | Add CI for the quality entry point, static JSON/shell/Python checks, and image/verifier contract test. Keep real-machine tests out of CI. | CI PR. |

**Acceptance criteria.**

- The register assigns every non-platform family a status: platform-owned, migration candidate, or compatibility-only, with its proof and rollback condition.
- One selected family proves that no caller-supplied command surface was introduced and that catalog/approval behavior is equivalent in its owner repository.
- A fresh local environment can install declared test tooling and run one documented quality command that executes the 50-plus suite and static checks.
- CI runs that quality command on every proposed change and does not require T480 credentials, Docker access, or ignored files.
- No legacy operation is removed until consumer evidence and rollback documentation meet the existing migration rule.

**Validation.** Run the new quality command locally from a clean environment, confirm it fails usefully without required tooling, and test catalog mismatch/approval-negative cases. Validate CI from a non-secret branch or PR. Any real T480 consumer proof remains a separate evidence task.

**Release and recovery.** Release documentation/tooling first, then one compatibility transfer. Version `t480_core` or record the exact shared revision used by a consumer. Keep the legacy operation through the agreed overlap window; rollback means re-enable the proven legacy catalog entry and pin the prior shared-core revision, not copy a transport implementation.

**Operational authorization.** Local and CI configuration changes are repository work. Any modifications in a sibling repository, package publication, or T480 consumer validation need that repository owner's authorization and its existing live-operation gates.

**Exit gate.** The quality command and CI are green; the register is complete; one transfer has evidence or is explicitly deferred. Pause if the target consumer cannot supply an owner or safe rollback path.

## Wave 4 — Tailnet policy readiness

**Objective and value.** Prepare a least-privilege policy artifact for review without creating tailnet access. Before: M10 commands reference a policy file that does not exist. After: a reviewer can assess a safe template before any identity or network mutation.

**Scope.** Address F-009 in `tailscale/policies/`, Tailscale documentation, and offline policy tests/fixtures. Exclude OAuth credential use, policy apply, device enrollment, firewall changes, device identifiers, and all M10 execution.

**Preserved strengths.** S-001, S-003, S-004, and S-005. Keep the adapter's fixed API surface, explicit approval, no public ingress, and device-specific iPhone constraint.

**Prerequisites.** Wave 0 policy clarification and an owner decision on the intended T16 service ports. M5 remains a hard prerequisite for M10 live remote-access proof, but not for an offline template.

| Task | Change approach | Effort / PR boundary |
| --- | --- | --- |
| W4-T1 | Add a commented deny-by-default HuJSON template using placeholders, with separate T16 development and iPhone dashboard-only examples. | Small policy/documentation PR. |
| W4-T2 | Add offline validation fixtures that reject broad user-wide iPhone rules, route/exit-node grants, public exposure assumptions, and missing placeholders. | Same PR. |
| W4-T3 | Update the M10 prompt/runbook to require an identity inventory, selected ports, owner MFA/recovery evidence, M5 proof, and independent review before replacing placeholders or applying policy. | Same PR. |

**Acceptance criteria.**

- The referenced policy file exists, parses offline, contains no real IDs, addresses, domains, credentials, or user-wide iPhone allow rule.
- Tests reject a template that enables routes, exit nodes, broad source access, or unapproved service ports.
- Documentation clearly distinguishes policy review from policy application and states that M10 remains unproven until its live evidence gates pass.

**Validation.** Run local template/parser tests and the Wave 3 quality command once available. The existing `validate-policy` and `apply-policy` commands are not invoked during this wave. Future live validation is the M10 evidence sequence, including cellular denial tests and revocation.

**Release and recovery.** A template is additive and can be reverted normally. If a future applied policy causes access loss, use retained LAN/local-console recovery and the versioned prior policy; do not depend on the tailnet itself for recovery. Actual apply/revert remains an explicitly approved live operation.

**Operational authorization.** All Wave 4 tasks are local review work. Policy apply and device authorization retain the adapter's `--approve` requirement plus explicit operator authorization.

**Exit gate.** The template and negative tests pass, and reviewers can identify exactly what remains before M10. Pause if intended T16 ports or recovery ownership are unresolved.

## Traceability

| Finding | Disposition | Reason |
| --- | --- | --- |
| F-001 | Wave 0: W0-T1, W0-T2 | A source-of-truth and privacy issue that must be corrected before operational changes. |
| F-002 | Wave 0: W0-T3, W0-T4 | Current evidence verification is directly contradicted by current configuration. |
| F-003 | Wave 1: W1-T1 through W1-T5 | Full-lab recovery needs design, protected storage, tooling, and real proof. |
| F-004 | Wave 2: W2-T1 through W2-T3 | Preserve intended redacted publication but make it explicit and operationally legible. |
| F-005 | Wave 1: W1-T3 | A migration ledger and tests prevent future drift before application schemas arrive. |
| F-006 | Wave 3: W3-T1, W3-T2 | Compatibility remains until one family proves safe ownership transfer. |
| F-007 | Wave 3: W3-T3, W3-T4 | The test suite needs a declared, repeatable execution path. |
| F-008 | Wave 2: W2-T4; deferred implementation | Measure first; no resource/runtime change is justified yet. |
| F-009 | Wave 4: W4-T1 through W4-T3 | Add offline readiness only; M10 remains a separately gated live effort. |

## Milestone alignment

| Milestone | Relationship to waves |
| --- | --- |
| M2 | Wave 0 repairs the evidence verifier; it does not re-prove M2. Wave 1's migration/recovery contract improves future M2-compatible deployments. |
| M3 | Wave 1 extends recovery scope beyond M3's intentionally synthetic PostgreSQL drill. It must preserve M3's current meaning and use a new full-stack evidence label. |
| M5 | Wave 1 supplies recovery prerequisites. Wave 0 resolves the S4U/Local System wording before M5 implementation or evidence changes. |
| M6 | Wave 0 directly supports `validation_integrity_corrected`; image upgrades still require official release/advisory review and M6 raw evidence. |
| M7–M9 | Wave 2 clarifies the monitoring boundary and improves safety/freshness semantics. It does not treat unit tests as their required real T480/T16 evidence. |
| M10 | Wave 4 prepares a policy artifact only. Device enrollment, policy application, external access, and revocation stay within M10's approval and evidence gates. |

## First implementation slice

Start with **W0-T1 and W0-T2** in one documentation-only PR: add the canonical exposure matrix, remove the tracked PostgreSQL address, update the four conflicting references, and add a small link/text regression test if useful. The PR succeeds when all docs identify loopback PostgreSQL/n8n as the baseline, dashboard LAN access is clearly conditional on host policy, no private address is tracked, and the existing 50-test suite plus static checks pass. It changes no runtime configuration or live setting.

## Reusable execution prompts

### Wave 0 prompt

```text
Execute only Wave 0 in docs/repo-improvement-waves.md: W0-T1 through W0-T4 for findings F-001 and F-002. Re-read docs/repo-deep-dive.md, the current Compose file, .env.example, exposure-related docs, scripts/verify-m2-evidence.sh, M6 registry text, and tests before changing anything. Preserve loopback PostgreSQL/n8n defaults, digest pinning, historical evidence interpretability, fixed operation contracts, and existing user work. Do not contact the T480, run adapters, start Docker, modify firewall/network settings, pull images, or change live evidence. Implement the canonical exposure policy, remove tracked private addresses, version or parameterize the M2 verifier without invalidating historical bundles, and add regression tests. Run the Wave 0 validation commands and report their results. Stop only when the Wave 0 exit gate passes; otherwise report the exact failing gate and leave later waves untouched. For any future live reachability check, identify the existing approval-gated operation rather than running it. Include rollback instructions for verifier/fixture changes in the PR handoff.
```

### Wave 1 prompt

```text
Execute only Wave 1 in docs/repo-improvement-waves.md: W1-T1 through W1-T4 for findings F-003 and F-005. First confirm Wave 0's exit gate in current files and re-read docs/repo-deep-dive.md, compose.yaml, backup/recovery scripts, migrations, adapter code, and milestone rules. Do not access .env, live volumes, remote adapters, databases, off-host storage, or T480 services unless a separately explicit operator approval is supplied. Produce the recovery inventory and implement only local, synthetic, reviewable tooling and tests. Preserve secrets outside Git, M3's isolated proof, named-volume safety, and migration idempotence. Do not delete backups or create a live restore target. Add clear release, failure, and forward-fix behavior. Run local validation. Stop at the live-drill boundary and hand off the exact approved operations, evidence bundle, and recovery prerequisites needed for W1-T5; do not run them.
```

### Wave 2 prompt

```text
Execute only Wave 2 in docs/repo-improvement-waves.md: W2-T1 through W2-T3, then perform W2-T4 only as a proposed read-only measurement plan unless separately authorized. Confirm Wave 0's exit gate and the Wave 1 recovery preflight before any migration-related implementation. Re-read the deep dive, monitoring code, dashboard code, Healthcheck flow, schedule configuration, tests, and operations docs. Preserve the static redacted dashboard, no control routes, no automatic remediation, disabled scheduler, and distinct approval-gated recovery path. Make persistence/publication side effects explicit and make no-data/stale/server-liveness states distinguishable. Add negative tests. Do not invoke adapters, apply migrations, start services, enable a scheduler, change firewall settings, or access live records. Run local tests and report the separate T480/T16 evidence required to complete the live validation gate. Do not begin Wave 3 or Wave 4.
```

### Wave 3 prompt

```text
Execute only Wave 3 in docs/repo-improvement-waves.md: W3-T1 through W3-T4 for findings F-006 and F-007. Confirm Wave 0's exit gate and re-read the deep dive, shared-core migration notes, current adapter/catalog, package metadata, and tests. Keep the fixed-operation and strict-host-key boundary intact. Create the ownership/deprecation register, declare a reproducible developer test environment and one quality command, and add CI that runs only non-secret local checks. Transfer at most one read-only operation family and only if its owning repository, owner, contract tests, and rollback path are available; otherwise document it as deferred rather than deleting or duplicating code. Do not access sibling-repository state without authorization, publish packages, run remote adapters, or remove compatibility operations. Run the new quality command locally and report CI setup and all remaining live proof requirements.
```

### Wave 4 prompt

```text
Execute only Wave 4 in docs/repo-improvement-waves.md: W4-T1 through W4-T3 for finding F-009. Confirm Wave 0's policy baseline, then inspect current Tailscale docs, adapter validation, catalog, M10 registry, and the policy directory. Add only a commented offline deny-by-default template and tests with placeholders; do not add real device/user IDs, IPs, credentials, routes, exit nodes, or an apply action. Preserve device-specific iPhone restrictions and existing approval gates. Do not create OAuth credentials, enroll devices, query or change the tailnet, apply policy, alter firewall rules, or test external access. Run offline validation and report the exact M5/M10 evidence and approved operations that must happen later. Stop when the Wave 4 exit gate passes.
```

## Remaining decisions

| Decision | Recommended default | Evidence needed |
| --- | --- | --- |
| PostgreSQL audience | Keep loopback-only; use governed adapters for administration. | A concrete application/client need and a T480/T16 exposure drill before any LAN exception. |
| Full-recovery storage | Use an encrypted, operator-controlled off-host destination with documented restore access. | Recovery inventory, threat model, retention/RPO decision, and clean synthetic restore proof. |
| Dashboard freshness | Show `stale` after a conservative explicitly chosen threshold; do not imply health from HTTP liveness. | Observed normal Healthcheck cadence and operator tolerance for delayed status. |
| Migration mechanism | Adopt a small checksum ledger before product schemas expand. | Fresh/upgrade/rerun/failure tests and a reviewed rollout plan. |
| First ownership transfer | A read-only, low-coupling operation family. | Named consumer owner, contract test, and reversible real-machine proof. |
| Resource limits/dashboard image | Defer any change. | Read-only T480 baseline and peak capacity data showing a real contention or upgrade-coupling problem. |
