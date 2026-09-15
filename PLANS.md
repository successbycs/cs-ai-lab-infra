# Codex Execution Plans (ExecPlans)

This file defines an ExecPlan: a self-contained, living specification that an
agent with only the current working tree and that plan can use to deliver an
observable, working infrastructure change. It is the planning and memory layer
of this repository's agent harness, alongside skills, tests, review, and
release gates.

An ExecPlan does not authorize live operations, destructive actions, external
communication, or commits. [AGENTS.md](AGENTS.md) and
[AGENT-WORKFLOW.md](AGENT-WORKFLOW.md) still govern those boundaries.

## When to use an ExecPlan

Create an ExecPlan before implementation when work is multi-step or multi-file,
introduces a feature or refactor, spans components, changes a durable service
boundary, or is likely to take more than an hour. It is optional for a small,
self-contained edit; state why it is unnecessary when that is not obvious.

Store each new plan at `plans/<short-action-name>.md`, using
[`plans/TEMPLATE.md`](plans/TEMPLATE.md). Existing component notes remain where
they are; migrate them when they next become the active execution plan rather
than creating duplicate histories.

## Lifecycle and storage

Every ExecPlan declares one status directly below its opening: `proposed`,
`active`, `blocked`, or `complete`.

- **Proposed:** researched enough to review, but implementation has not begun.
- **Active:** implementation or approved investigation is under way.
- **Blocked:** a specific external decision, authority, or state prevents the
  next safe step; record it in `Progress` and `Outcomes & Retrospective`.
- **Complete:** all planned outcomes and acceptance evidence are recorded, or
  any deliberately excluded remainder is explicitly handed off.

Keep proposed, active, and blocked plans in `plans/`. Move completed plans to
`plans/archive/` only after their outcomes are recorded. The validator checks
the required structure of every plan in both locations so history remains
resumable; status tells an agent whether it is current work.

## Non-negotiable requirements

- **Self-contained:** define repository terms, exact paths, commands, expected
  observations, and acceptance evidence. Links can provide supporting detail,
  but a future agent must not need prior chat, an earlier plan, or unstated
  tribal knowledge to resume safely.
- **Living:** update `Progress`, `Surprises & Discoveries`, `Decision Log`, and
  `Outcomes & Retrospective` as work proceeds. At every stopping point, record
  what is complete, the next safe step, and any blocker.
- **Outcome-oriented:** describe the behavior or operational state a user can
  observe. A code diff, successful command, or green parser alone is not a
  completed outcome.
- **Bounded:** describe explicit non-goals, authorization gates, data and
  network constraints, rollback, and recovery. Do not place secrets, private
  topology, customer data, raw logs, or generated evidence in a plan.
- **Verifiable:** every milestone must incrementally produce a result that can
  be checked independently. Use [QA verification](QA-VERIFICATION.md) and the
  relevant component's documented evidence path.

## Authoring an ExecPlan

Read this file end to end before drafting or materially revising a plan. Start
from the template, then inspect the repository and relevant component
documentation until the plan is accurate.

Write for a capable newcomer to this repository. Name the files and symbols to
change, explain how the current behavior works, and tell the reader what each
command proves and what a failure means. Prefer small, additive, reversible
steps. For uncertain designs, include a bounded prototype or spike with its
promotion/discard criteria rather than presenting speculation as fact.

Milestones tell the implementation story: for each, explain the purpose, the
work, the expected result, and the independently observable proof. `Progress`
tracks granular execution separately with timestamped checkboxes. Do not make
milestones a task list with no acceptance condition.

## Executing an ExecPlan

Read the plan and the referenced repository material before acting. Proceed to
the next safe milestone without asking for generic “next steps,” but stop for
explicit user direction wherever policy requires approval. Keep the plan true:

1. Update progress when a granular step completes or splits.
2. Record an unexpected behavior in `Surprises & Discoveries`, including the
   concise evidence and its consequence.
3. Record a material design choice and rationale in `Decision Log`; also update
   `docs/decisions.md` when it is a lasting architectural decision.
4. If scope changes, revise the plan before continuing and explain the change
   in the decision log.
5. At completion, record the observed outcome, acceptance evidence, remaining
   gaps, and lessons in `Outcomes & Retrospective`.

Use parallel paths only when they reduce risk. State how each path is validated
and how the obsolete path is retired without data loss. Keep prototypes
additive and isolated from live state unless separately authorized.

## Mechanical plan gate

Run `make execplan-check` (or `python3 scripts/validate_execplan.py`) after
creating or revising a plan. `make quality` includes this check. The validator
checks the required living-plan structure for `plans/*.md`; it cannot judge the
truth or sufficiency of the plan, so review and acceptance evidence still
matter.

## Required ExecPlan structure

Every active plan must contain the headings in
[`plans/TEMPLATE.md`](plans/TEMPLATE.md):

1. `Purpose / Big Picture`
2. `Progress`
3. `Surprises & Discoveries`
4. `Decision Log`
5. `Outcomes & Retrospective`
6. `Context and Orientation`
7. `Plan of Work`
8. `Concrete Steps`
9. `Validation and Acceptance`
10. `Idempotence and Recovery`
11. `Artifacts and Notes`

The opening must identify the document as a living ExecPlan maintained under
this `PLANS.md`, followed by a valid `Status:` line. `Progress` must use
timestamped checkboxes and always reflect the actual state of the work.
