---
name: execplan-management
description: Author, execute, update, or review self-contained living ExecPlans for substantial repository work.
---

# ExecPlan management

Use for a multi-step or multi-file change, new feature, refactor,
cross-component operation, or work likely to take more than an hour. Read
[PLANS.md](../../../PLANS.md) in full before creating, revising, or executing
an ExecPlan.

- Create the plan at `plans/<short-action-name>.md` from
  [`plans/TEMPLATE.md`](../../../plans/TEMPLATE.md). It must enable a new agent
  with only the working tree and plan to resume safely.
- State observable outcomes, exact affected paths and commands, constraints,
  non-goals, approval gates, recovery, and acceptance evidence. A diff or
  command exit status is not an outcome.
- Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes &
  Retrospective` accurate at every stopping point. Split partial work into
  completed and remaining entries instead of leaving ambiguous status.
- Continue to the next safe milestone autonomously, but do not infer authority
  for a live mutation, destructive step, external action, or commit.
- Run `make execplan-check` after changing a plan and use
  [QA verification](../../../QA-VERIFICATION.md) for acceptance evidence.

For a material plan review, use `infrastructure-review` to assess whether the
plan preserves the repository's access, network, secret, and runtime
boundaries; the structural validator alone cannot establish that.
