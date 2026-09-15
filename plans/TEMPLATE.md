# <Short, action-oriented description>

This ExecPlan is a living document. Maintain it in accordance with
[`PLANS.md`](../PLANS.md). Keep `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

Status: proposed

## Purpose / Big Picture

Describe the observable outcome, who benefits, and how a user or operator can
see it working. State scope and non-goals.

## Progress

- [ ] (YYYY-MM-DD HH:MMZ) Describe the first independently meaningful step.

## Surprises & Discoveries

- None yet. Record unexpected behavior, concise evidence, and its consequence.

## Decision Log

- (YYYY-MM-DD) Decision: <choice>. Rationale: <why it is appropriate>.

## Outcomes & Retrospective

Describe the achieved behavior, evidence, remaining gaps, and lessons at
completion. While active, state the next safe step.

## Context and Orientation

Explain the current behavior, relevant components, exact repository paths,
terms, and constraints a newcomer needs. Include only non-secret topology and
configuration information.

## Plan of Work

Describe the milestones as a narrative. For each milestone, state the purpose,
the change, expected result, and independently observable proof. Identify
approval gates before any live or destructive operation.

## Concrete Steps

List exact files, functions, commands, and expected observations in execution
order. Explain what each command proves and what to do if it fails.

## Validation and Acceptance

Map each acceptance criterion to the test or evidence that establishes it.
Include normal, failure, and boundary behavior where relevant. Link to
non-secret local evidence rather than embedding raw output.

## Idempotence and Recovery

State which steps are safe to repeat, the retry stopping condition, rollback or
recovery procedure, and precautions for persistent data or live services.

## Artifacts and Notes

List tracked files, protected local evidence locations, concise sample output,
and other handoff details needed to resume. Never include credentials, private
addresses, customer data, or raw sensitive logs.
