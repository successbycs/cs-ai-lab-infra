# Harden agent governance and pause backup creation

This ExecPlan is a living document. Maintain it in accordance with
[`PLANS.md`](../PLANS.md). Keep `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

Status: active

## Purpose / Big Picture

Correct the approved review findings in agent-facing guidance, make the
ExecPlan gate enforce its stated contract, define a plan lifecycle, broaden the
repository's stated scope to an AI Lab, and pause all
backup-producing paths until additional T480 disk capacity is attached.

The observable result is that agents receive safe non-secret Compose validation
guidance, understand that T16 access uses approved private paths, create plans
with unambiguous lifecycle states, and receive a clear, deterministic refusal
when attempting a paused backup operation.

Scope: tracked documentation, local validators/tests, and backup-producing
scripts or adapter paths. Non-goals: attaching storage, deleting existing
backups, deploying a change to the T480, changing firewall policy, or resuming
backups without a later explicit decision.

## Progress

- [x] (2026-09-15 00:00Z) Created this ExecPlan and identified the reviewed
  Compose-secret, T16-access, lifecycle, and backup-scope findings.
- [x] (2026-09-15 00:00Z) Inventoried backup-producing paths and introduced a
  fail-closed pause control with clear operator recovery guidance.
- [x] (2026-09-15 00:00Z) Corrected agent guidance, ExecPlan validation, and
  lifecycle semantics with focused tests.
- [x] (2026-09-15 00:00Z) Validated all affected paths and recorded the outcome.

## Surprises & Discoveries

- No tracked recurring scheduler invokes `scripts/backup.sh`; the tracked paths
  are manual scripts and explicit adapter operations. A pause must therefore
  guard execution rather than disable a scheduler.

## Decision Log

- (2026-09-15) Decision: model T16 access as an approved private access path,
  not a requirement to publish every service directly to the LAN. Rationale:
  this preserves the loopback-only database and n8n boundary.
- (2026-09-15) Decision: use explicit `proposed`, `active`, `blocked`,
  `complete`, and `archived` ExecPlan states. Rationale: the quality gate must
  know which plans are current without losing historical handoff records.
- (2026-09-15) Decision: pause backup creation fail-closed until a later owner
  decision records additional T480 storage and explicitly removes the pause.
  Rationale: available disk is currently insufficient for further backup growth.

## Outcomes & Retrospective

Completed. The pause guard blocked all five backup-producing scripts before
data creation; 14 focused tests and the 118-test repository suite passed.
Remaining operational work is explicitly deferred until additional T480 storage
is attached and a later owner-approved resume change is made.

## Context and Orientation

`AGENTS.md`, `AGENT-WORKFLOW.md`, `PLANS.md`, `QA-VERIFICATION.md`, and
`RELEASE-READINESS.md` provide the repository's agent harness. The review found
that raw `docker compose config` can print resolved secrets, the current plan
validator only searches for substrings, and no lifecycle distinguishes current
from historical plans.

The root Compose project includes Plane and interpolates protected files. The
T480 holds private services; the T16 is the interactive operator machine.
T16 reachability must be satisfied through a documented private transport or
component adapter rather than opening database or n8n services to the LAN.

Existing PostgreSQL, full-lab, M3 recovery, and Penpot backup scripts create
disk-consuming files. The repository has no tracked periodic backup schedule.
The implementation must stop new backup creation before a command allocates
data, while preserving read-only manifest verification and leaving existing
backups untouched.

## Plan of Work

Milestone 1 makes the backup pause real. Identify each creator, add a shared
or consistently applied guard, and document that upgrades or drills requiring
a new backup are blocked. The proof is a safe, deterministic pause message
before any container or archive action.

Milestone 2 corrects the agent harness. Replace secret-printing Compose advice
with quiet validation, formalize plan status and archive behavior, and strengthen
the validator to parse exact H2 sections and timestamped Progress checkboxes.
The proof is focused tests that reject malformed plans and safe command guidance
that does not render resolved secrets.

Milestone 3 aligns the AI Lab purpose and access language. Update only the
repository-level language that is now out of scope, retain component security
policies, and link the T16-access requirement to approved private paths. The
proof is review of the resulting documentation links and policy consistency.

## Concrete Steps

1. Search `scripts/`, `penpot/scripts/`, and `t480_adapter.py` for every path
   that creates a backup, recovery archive, or synthetic recovery dump. Record
   which are blocked and which read-only verification paths remain available.
2. Add the pause guard and a tracked non-secret operator document stating the
   reason, effective scope, and explicit resume prerequisites. Run each script's
   smallest safe preflight or focused test to demonstrate refusal before writes.
3. Change guidance from `docker compose config` output to quiet configuration
   validation. When a binding must be reviewed, use source-level inspection or
   redacted output only.
4. Define lifecycle statuses and archive layout in `PLANS.md` and the template.
   Update the validator and its tests to enforce exact headings, a status, and
   timestamped checkboxes specifically under `Progress` for active plans.
5. Align repository-level agent guidance with AI Lab language. Update
   architecture access wording to require an
   approved private T16 path, without changing network exposure policy.
6. Run focused tests, `make execplan-check`, documentation-link checks, and
   `make quality`. Update this plan with actual outcomes; do not deploy or
   resume backups.

## Validation and Acceptance

- A raw resolved Compose configuration is not required by any agent skill;
  quiet validation is the default documented command.
- Validator tests prove malformed headings, missing plan status, and a checkbox
  outside Progress fail; a compliant active plan passes.
- The lifecycle document explains when a plan is proposed, active, blocked,
  complete, or archived and what `make execplan-check` scans.
- Each identified backup-producing path refuses before creating data while the
  pause is active; existing manifest verification remains read-only.
- AI Lab and approved-T16-path language is consistent with the network policy.
- `make quality` passes without starting services or exposing secrets.

## Idempotence and Recovery

Validation and documentation checks are read-only. A pause guard must be safe
to invoke repeatedly and must not delete data. Resuming is a future, explicit
change after storage attachment and a disk-capacity check; it requires removing
the guard through the documented controlled procedure, not bypassing it with an
environment variable or direct container command.

## Artifacts and Notes

Expected tracked artifacts include the agent-harness Markdown files, backup
scripts/adapter code, `scripts/validate_execplan.py`, its tests, and a
non-secret backup-pause record. The plan must not contain storage paths,
credentials, or raw host evidence.
