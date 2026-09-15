# Agent workflow

Use this workflow for changes in this infrastructure repository. It complements
the repository-wide requirements in [AGENTS.md](AGENTS.md); neither document
authorizes a live or destructive operation that the user has not requested.

## 1. Understand and scope

1. Identify the requested outcome, affected component, and whether the work is
   read-only, a repository edit, or a live T480/service mutation.
2. Read [AGENTS.md](AGENTS.md), the nearest component README, and the smallest
   applicable skill in [`.codex/skills`](.codex/skills/).
   Read [the architecture](docs/architecture.md) as well when the work affects
   service boundaries, data flow, networking, runtime roles, or portability.
3. Inspect the working tree before editing. Preserve unrelated user changes.
4. For a new AI or automation flow, use `workflow-design` first to define
   inputs, boundaries, human approval, failure behavior, and acceptance checks.

## 2. Plan the safe change

1. Keep the change focused and reversible. Identify any configuration, port,
   recovery, or operator-documentation update it requires.
   For work that meets the ExecPlan threshold in [PLANS.md](PLANS.md), create
   `plans/<short-action-name>.md` from
   [`plans/TEMPLATE.md`](plans/TEMPLATE.md) before implementation. Keep a
   small, scoped change in the task discussion instead.
2. Treat secrets, local state, private topology, and generated evidence as
   untracked material. Use `secrets-and-config` for any configuration path.
3. When an operation affects the T480, use the narrowest supported
   `t480_adapter.py` operation; do not introduce free-form remote commands.
4. Obtain explicit user direction before a live mutation, external message,
   runtime lifecycle action, destructive cleanup, or data restore.
5. Treat the ExecPlan as a living handoff: update its progress, discoveries,
   decisions, and outcomes before pausing, changing approach, or handing off.

## 3. Implement

1. Make the smallest change that satisfies the request.
2. Preserve loopback-only service boundaries and named volumes. Use the
   component-specific skills for Plane, Penpot MCP, n8n, Compose, recovery, and
   network work.
3. Update the relevant documentation when operator behavior, access, ports,
   lifecycle, or recovery procedure changes.
4. Add an entry to `docs/decisions.md` when the change makes a material,
   lasting architectural choice.

## 4. Assure and review

1. Use `quality-assurance` to choose coverage from requirements and risks.
   Follow [QA verification](QA-VERIFICATION.md) to distinguish completed
   evidence from planned or unavailable checks.
2. Run `infrastructure-verification` checks proportionate to the changed
   surface: targeted tests and syntax checks first, then `make quality` and
   resolved Compose validation where applicable.
3. For claims about reachability, recovery, workflow behavior, or persistence,
   obtain the component's appropriate end-to-end evidence. Static validation
   does not prove live behavior.
4. Use `infrastructure-review` before handoff for material or cross-component
   changes; report confirmed findings separately from residual uncertainty.
5. For an authorized deployment or operational release, complete the applicable
   checks in [release readiness](RELEASE-READINESS.md) before performing the
   live change.

## 5. Hand off

1. State what changed, the user-visible or operational outcome, validation
   performed, and meaningful checks not run.
2. Link the changed tracked files. Do not include secrets, private addresses,
   raw host output, customer data, or local-only paths in the handoff.
3. Commit only when asked. Stage only the requested scope and report the commit
   identifier after it succeeds.
