# Introduce a living ExecPlan process

This ExecPlan is a living document. Maintain it in accordance with
[`PLANS.md`](../PLANS.md). Keep `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

Status: complete

## Purpose / Big Picture

Give this infrastructure repository a durable planning process for substantial
agent work. After this change, a future agent can create a self-contained plan,
resume it without prior chat context, validate that it has the required living
sections, and use existing QA/release gates to prove an observable outcome.

Scope: repository documentation, a template, a structural validator, tests,
and agent-skill routing. Non-goals: installing a third-party harness product,
creating CI infrastructure, changing live services, or retroactively rewriting
historical component plans.

## Progress

- [x] (2026-09-15 00:00Z) Reviewed the existing agent workflow, plans, QA,
  release, skills, and quality target.
- [x] (2026-09-15 00:00Z) Defined the ExecPlan contract, template, routing,
  skill, and a `make` gate.
- [x] (2026-09-15 00:00Z) Added the structural validator and focused tests.
- [x] (2026-09-15 00:00Z) Ran the focused validator tests, skill and link
  validation, and repository quality checks; all passed.

## Surprises & Discoveries

- The repository already has a component-local Penpot execution plan at
  `penpot/EXECPLAN-durable-mcp.md`. It predates this shared process, so moving
  it would create unnecessary historical churn; it will migrate only if it
  becomes active work again.

## Decision Log

- (2026-09-15) Decision: store new active ExecPlans in `plans/` and retain
  `PLANS.md` at the repository root. Rationale: the root document is
  discoverable by agents, while the directory separates active execution
  records from component documentation.
- (2026-09-15) Decision: gate required headings and living-plan markers with a
  local Python validator that `make quality` runs. Rationale: it makes the
  process observable without claiming that structure proves correctness.
- (2026-09-15) Decision: retain human/agent review and component acceptance
  evidence as separate gates. Rationale: structural validation cannot prove
  network reachability, data recovery, or live service behavior.

## Outcomes & Retrospective

The repository now has a self-contained ExecPlan contract, template, active
plan location, structural validator, quality gate, focused tests, and a
discoverable `execplan-management` skill. Validation observed:

- `python3 scripts/validate_execplan.py` accepted this active plan.
- `python3 -m pytest -q tests/test_validate_execplan.py` passed 2 tests.
- All 13 repository skills passed metadata validation and 20 linked documents
  or skill files resolved.
- `make quality` passed all 117 tests plus shell, Python compilation, JSON, and
  ExecPlan checks.

Remaining limitation: the validator proves plan structure only. The QA,
component-specific, infrastructure-review, and release-readiness gates remain
responsible for evaluating whether a plan's evidence and operational outcome
are sufficient.

## Context and Orientation

`AGENTS.md` is the repository-wide policy and routes agents to skills.
`AGENT-WORKFLOW.md` describes scope through handoff. `QA-VERIFICATION.md` and
`RELEASE-READINESS.md` define evidence and release decision inputs. Before this
change, `PLANS.md` provided only a lightweight generic template and no
mechanical validation.

The new process uses `PLANS.md` as the normative contract,
`plans/TEMPLATE.md` as the copyable structure, and
`scripts/validate_execplan.py` as a deterministic structural check. The
validator scans active Markdown plans in `plans/`, skipping its README/template
files, and requires named headings, a living-document declaration, a reference
to `PLANS.md`, and at least one checkbox. It intentionally does not read or
operate private runtime configuration.

## Plan of Work

Milestone 1 establishes the contract and discovery path. It adds the detailed
ExecPlan requirements to `PLANS.md`, tells agents in `AGENTS.md` and
`AGENT-WORKFLOW.md` when to create one, and adds the `execplan-management`
skill. The result is that substantial work has a known durable home and a
resumable format. Proof is documentation-link and skill validation.

Milestone 2 makes the contract mechanically visible. It adds the template,
validator, focused tests, and `execplan-check` Make target. The result is that
an incomplete active plan fails locally and in `make quality`. Proof is the
focused test and validator output.

Milestone 3 connects the plan to outcomes rather than process theater. It adds
QA/release references and validates the entire repository quality target. The
result is that a plan's structure is a gate, while component-specific proof
remains the release criterion. Proof is the successful quality run and this
plan's completed outcome record.

## Concrete Steps

1. Replace the generic `PLANS.md` guidance with the ExecPlan contract and
   required headings. Check links with a Markdown-link script and whitespace
   with `git diff --check`.
2. Add `plans/TEMPLATE.md` and this plan. Run
   `python3 scripts/validate_execplan.py`; expected output includes
   `EXECPLAN_VALID plans/introduce-execplan-process.md` and
   `EXECPLAN_CHECK_OK`.
3. Add `scripts/validate_execplan.py` and
   `tests/test_validate_execplan.py`. Run
   `python3 -m pytest -q tests/test_validate_execplan.py`; expected result is
   two passing tests. If it fails, correct the validator or test rather than
   weakening required headings without a documented decision.
4. Add `execplan-check` to `Makefile`, then run `make quality`. It must execute
   the plan gate before the existing test, shell, Python, and JSON checks. If a
   check fails due to pre-existing unrelated work, record the exact failure and
   do not misrepresent the process as fully verified.
5. Update this plan's Progress and Outcomes with actual command results. Do not
   commit unless requested.

## Validation and Acceptance

- An active plan with all required headings, living declaration, `PLANS.md`
  reference, and checkbox passes the validator; covered by
  `test_validator_accepts_complete_plan`.
- An incomplete plan fails with a missing-heading diagnostic; covered by
  `test_validator_rejects_incomplete_plan`.
- `make execplan-check` validates this plan and produces its success marker.
- `make quality` includes `execplan-check` and continues to run existing
  repository checks.
- Every new documentation and skill link resolves; all skills, including
  `execplan-management`, pass their metadata validator.

## Idempotence and Recovery

The validator and test commands are read-only and safe to repeat. Adding or
editing an ExecPlan is reversible through a normal Git edit. `make quality`
does not start services or alter runtime state. If a new plan fails validation,
restore its required sections from `plans/TEMPLATE.md`; do not bypass the gate.

## Artifacts and Notes

Tracked artifacts: `PLANS.md`, `plans/TEMPLATE.md`, this plan,
`scripts/validate_execplan.py`, `tests/test_validate_execplan.py`, `Makefile`,
`AGENTS.md`, `AGENT-WORKFLOW.md`, `QA-VERIFICATION.md`,
`RELEASE-READINESS.md`, and `.codex/skills/execplan-management/SKILL.md`.

The plan contains no secrets, private addresses, raw host output, or live
runtime instructions. It relies on existing component skills for any later
service-specific ExecPlan.
