# Repository deep dive and improvement waves

Use this prompt from the root of `cs-ai-lab-infra` when explicitly starting or resuming the review goal. Reading, reviewing, or editing this file alone does not authorize execution.

## Goal objective

Copy the following objective when you choose to start the goal:

```text
Complete the repository review and improvement-wave plan defined in
t480/prompts/repo-deep-dive.md. Produce docs/repo-deep-dive.md and
docs/repo-improvement-waves.md with evidence-backed strengths and weaknesses,
prioritized findings, dependency-aware waves, acceptance and rollback plans,
and an execution prompt for each wave. Complete the prompt's review completion
checklist and provide the final handoff. Do not implement the recommendations,
execute the waves, or change live infrastructure.
```

---

## Execution prompt

Act as a senior infrastructure engineer, security reviewer, and pragmatic maintainer. Perform a deep, evidence-based review of this repository. Identify its strengths, weaknesses, and operational unknowns, then produce an actionable plan to improve it through sequenced **Waves** of updates.

Work toward completion of the review and plan using the completion checklist below. Do not implement the proposed changes or execute the waves. If the work spans sessions, resume from the existing draft documents and recorded baseline; recheck changed evidence instead of restarting the review.

## Project context and review standard

This repository supports a local-first, private Customer Success AI lab. Its documented architecture includes a T16 development/control workstation, a persistent T480 Windows/WSL runtime, Docker Compose, PostgreSQL with pgvector, n8n, optional Ollama, a health dashboard, and governed remote-operation adapters. The shared `t480_core` package also supports consumers in separate application repositories.

Verify that context against the checkout. Evaluate the repository against its actual purpose, hardware constraints, operator capacity, and current maturity. Prefer improvements that make Customer Success AI experimentation safer, more reliable, easier to maintain, or easier to reproduce. Do not recommend enterprise infrastructure, new services, or broad rewrites without evidence that their benefits justify the operating cost.

Identify good design choices worth preserving as carefully as you identify defects. Distinguish a deliberate tradeoff from an implementation bug, a documentation mismatch, an unproven operational claim, or an optional future enhancement.

## Scope and execution boundaries

- Read applicable `AGENTS.md` instructions. Record the branch, commit, and initial worktree status; preserve existing work.
- This task authorizes repository inspection, safe local validation, and creation of the review documents specified below. It does not authorize deployment or live infrastructure changes.
- Inspect commands and tests before running them. A command named `health`, `preflight`, `verify`, or `read-only` may still publish data, write files, fetch updates, or contact a remote system. Trace its actual behavior.
- Do not invoke remote adapters, access live databases or APIs, start services, pull images, run backup/restore drills, change firewall or tailnet settings, or activate schedules as part of this review. List necessary live checks as follow-up validation in the plan.
- Do not read or reproduce credentials, private environment files, customer data, database dumps, or ignored raw operational evidence. Use tracked templates and redacted documentation. Identify a suspected secret by location and type without printing its value.
- Run local checks only when they are isolated from live infrastructure and credentials. Record missing tools or unavailable environments as limitations; continue the review without claiming those checks passed.
- Do not modify runtime configuration, code, existing milestone state, or operational evidence. Limit repository edits to the requested review documents. Safe validation may create disposable temporary files or test caches, but must not overwrite existing operational artifacts. Do not commit, push, or publish the documents.
- Continue with reasonable stated assumptions. Ask only when a missing fact materially blocks a conclusion, and complete independent analysis while it remains unresolved.
- Missing live evidence, unavailable tools, and failing checks are review results to document, not authorization to fix the repository or expand the task. Record a specific follow-up check or improvement task where needed.

## Investigation approach

### 1. Establish the baseline

Inventory the tracked repository, entry points, dependencies, runtime definitions, configuration, tests, automation, and documentation. Record which areas were inspected in depth, sampled, or excluded, with reasons; do not claim exhaustive coverage of uninspected files or binary assets. Use targeted searches and inspect complete relevant functions and call paths; do not base conclusions solely on filenames, README statements, or search snippets.

Start with these paths where they still exist, then follow references and dependencies:

- `README.md`, `compose.yaml`, `.env.example`, `.gitignore`, and `pyproject.toml`.
- `docs/architecture.md`, `docs/setup.md`, `docs/operations.md`, `docs/backup-restore.md`, `docs/decisions.md`, `docs/cloud-portability.md`, and `docs/learning-roadmap.md`.
- `t480/README.md`, `t480/command-catalog.json`, `t480/tool-registry.json`, `t480/transport-config.json`, `t480/milestone-registry.json`, `t480/milestones.md`, `t480/next-session.md`, and the execution prompts.
- `t480_core/`, all adapters in `scripts/`, and the bootstrap, update, backup, health, evidence-capture, and evidence-verification scripts.
- `docs/t480-shared-core.md`, `docs/t480-adapter-migration.md`, and the provisioning/process logs, treating historical entries as dated claims.
- `postgres/init/`, `postgres/migrations/`, `monitoring/`, `n8n/`, `ollama/`, `tailscale/`, and `proxy/`.
- `tests/` and any CI, linting, dependency-management, or release configuration discovered in the checkout.

Draw a compact architecture and trust-boundary map. Explain where commands execute, how data and evidence move, what persists, and which interfaces are exposed. Separate repository-defined configuration from effective live settings that cannot be established locally.

### 2. Review the important dimensions

For each dimension, identify strengths, weaknesses, supporting evidence, and uncertainty:

1. **Purpose and architecture:** platform/application ownership, separation of concerns, coupling, legacy compatibility operations, shared-core boundaries, and scope drift relative to the Customer Success mission.
2. **Correctness and maintainability:** complexity, duplication, configuration validation, failure propagation, timeouts, quoting across Python/PowerShell/SSH/WSL/shell, idempotency, partial failures, and recovery behavior.
3. **Security and governance:** operation allowlists, approval enforcement at actual entry points, catalog/code agreement, host-key verification, path and argument validation, credential handling, redaction, audit integrity, database privileges, and network exposure.
4. **Runtime reliability:** Compose health semantics, service dependencies, optional-service behavior, startup and restart handling, Windows/WSL boot context, resource limits, and unattended operation on T480 hardware.
5. **Data and recovery:** initialization versus migrations on existing volumes, migration repeatability and failure handling, backup completeness, retention and off-host copies, n8n data and encryption-key recovery, and evidence that restores work. Distinguish a synthetic recovery drill from recovery of the complete live platform.
6. **Monitoring and evidence:** collection, normalization, persistence, rendering, dashboard freshness, degraded/unknown states, scheduling, alert usefulness, log growth, and whether milestone proof is independently verifiable. Distinguish an HTTP health endpoint from current evidence of service health.
7. **Testing and delivery:** reproducible developer setup, behavioral test coverage, failure-path coverage, tests that merely assert source text, missing integration boundaries, CI, packaging, image pinning, upgrade detection, rollback, and shared-package consumer compatibility.
8. **Documentation and operations:** consistency between README, architecture, scripts, catalogs, milestone definitions, and session notes; fresh-install usability; existing-install upgrades; reproducible runbooks; and clear ownership of deferred work.
9. **Portability and value:** machine-specific assumptions, contracts with sibling application repositories, migration options, and the smallest useful next improvements for AI workflows. Do not assume sibling repositories or their runtime state are available.

Investigate these repository-specific questions as hypotheses, not predetermined findings:

- Do documentation claims about PostgreSQL, n8n, and dashboard exposure agree with Compose defaults, environment templates, adapter operations, and firewall guidance? A wildcard bind does not by itself establish public reachability.
- Do commands described as read-only have persistence or publishing side effects, and are those effects consistent with the documented approval model?
- Do backup/recovery claims agree across scripts, milestone notes, and runbooks? Which capabilities are implemented, locally tested, documented as observed, or still unproven?
- Are init SQL and migration SQL consistent for both fresh and existing databases?
- Is the migration to `t480_core` complete at the intended boundaries, and what must be proven before legacy application operations can be removed?
- Do milestone dependencies and handoff notes agree, especially for no-logon recovery, upgrades, monitoring, and private remote access?

For version support, upgrade compatibility, or vulnerability claims, consult current official release notes, documentation, or security advisories. Cite their URLs and the date checked. Do not infer vulnerability from an old version number alone. If current verification is unavailable, say so and propose a verification task.

### 3. Validate and challenge the findings

Run appropriate safe local checks after reviewing their behavior, such as the existing Python tests, shell syntax checks, and JSON parsing. Validate Compose only with isolated, non-secret example configuration if tooling allows it; avoid loading a real `.env` or printing resolved secrets. Record exact commands, outcomes, and meaningful limitations.

For each material concern, trace a concrete failure scenario and look for mitigating controls before finalizing it. Cite repository-relative paths with line numbers and relevant symbols. Use multiple sources when alleging drift between documents and implementation.

Do not equate a passing mocked test with real-machine proof, a roadmap entry with an implemented feature, an unavailable environment with a product defect, or an uninspected area with an absence of problems. Document review coverage and exclusions.

## Required deliverables

Create `docs/repo-deep-dive.md` and `docs/repo-improvement-waves.md`. If either exists, read it first and update it carefully, preserving relevant unresolved work. Make the documents self-contained and specific enough for a maintainer who has not seen this conversation.

While working, label incomplete documents as drafts and keep a short progress checklist in them so an interrupted goal can resume. Record completed review areas, remaining checks, and unresolved questions without retaining raw operational data. Finalize the documents only after the completion checklist passes.

### A. `docs/repo-deep-dive.md`

Include:

1. **Executive assessment:** overall fitness for the lab's purpose, the most valuable existing capabilities, the most consequential weaknesses, and the next recommended action. Separate code quality from operational readiness.
2. **Scope and baseline:** review date, commit/branch, worktree caveats, inspected areas, architecture/trust boundaries, checks performed, and unavailable evidence.
3. **Strengths register:** stable IDs `S-001`, etc.; evidence; why each strength matters; and what later changes should preserve. Do not force a fixed count or invent positives for balance.
4. **Findings register:** stable IDs `F-001`, etc. For each finding provide:
   - Title and category: defect, security exposure, operational gap, documentation drift, maintainability issue, or enhancement.
   - Evidence and affected paths/symbols.
   - Concrete trigger or failure scenario and practical impact.
   - Evidence status: observed by local validation, supported by source inspection, documented historical claim, or hypothesis requiring validation.
   - Confidence, mitigating controls, and remaining uncertainty.
   - Priority: `P0` immediate credible danger/blocker; `P1` next substantive work; `P2` planned improvement; `P3` optional/deferred. Justify priority using impact, likelihood, and the lab context.
   - Smallest adequate remedy, likely scope, and validation needed.
5. **Documentation and milestone reconciliation:** conflicting claims, implementation evidence, and proposed corrections or follow-up checks. Reference existing `M0`–`M10` definitions where applicable; do not mark milestones proven.
6. **Preserve and defer:** explicit design choices to keep, accepted tradeoffs, and changes whose cost currently outweighs their value.

Do not use a numeric maturity score without an explained rubric. Prefer concrete conclusions over generic best-practice checklists.

### B. `docs/repo-improvement-waves.md`

Translate the findings into a dependency-aware delivery plan. Use `Wave 0`, `Wave 1`, etc., with outcome-oriented names. Choose the number of waves from the evidence; aim for roughly four to six when that fits. Each wave must deliver a coherent, independently verifiable improvement and leave the repository usable.

Wave 0 should address urgent containment or the minimum missing baseline needed for safe work, if warranted. Do not delay a credible urgent issue behind routine cleanup, and do not create empty waves to fill a template. Explain ordering and distinguish hard prerequisites from preferences.

Start with a compact roadmap table: wave, outcome, finding IDs, dependencies, rough effort range, change risk, and exit gate. State estimation assumptions and avoid unsupported calendar promises.

For **every wave**, specify:

- **Objective and value:** observable before/after behavior and why it matters now.
- **Scope:** findings addressed, likely files/components, and explicit exclusions.
- **Preserved strengths:** relevant `S-xxx` IDs and constraints the changes must maintain.
- **Prerequisites:** earlier waves, required evidence, external dependencies, and any applicable milestone gates. Distinguish repository improvements from live T480 work.
- **Ordered work packages:** concrete tasks with stable IDs such as `W1-T1`, change approach, estimated effort, and suggested PR boundaries. Prefer reviewable increments and avoid combining unrelated refactors with risky operational changes.
- **Acceptance criteria:** measurable pass/fail outcomes. Avoid criteria such as “improve security” or “update documentation” without a verifiable result.
- **Validation:** exact existing commands where established, proposed tests where missing, negative/failure cases, and any separate real-machine drill with the evidence it must produce. Clearly label proposed commands or tools that do not exist yet.
- **Release and recovery:** compatibility considerations, rollout order, backup/preflight requirements where relevant, rollback triggers and steps, and how recovery will be verified. A Git revert is insufficient when a change alters persistent data or live infrastructure; state irreversible aspects and a recovery or forward-fix plan.
- **Operational authorization:** identify the concrete live operations and existing repository approval requirements that would apply during execution. Keep ordinary local implementation and validation executable within their authorized scope.
- **Exit gate:** exactly what must pass before the next dependent wave starts, and what should cause a pause or replan.

Include these final sections:

1. **Traceability:** map every `F-xxx` to a wave/task, previously accepted risk, proposed deferral, or validation-only investigation, with a reason. Do not accept new material risks on the operator's behalf; label decisions still requiring an owner as pending. Deduplicate root causes and ensure no high-priority finding disappears from the plan.
2. **Milestone alignment:** show how waves support or depend on existing milestones without replacing their IDs, acceptance checks, or evidence requirements.
3. **First implementation slice:** identify the smallest useful PR to start with, its exact scope, acceptance checks, and expected result.
4. **Reusable execution prompts:** provide one self-contained, copyable prompt per wave. Each must identify the objective, finding/task IDs, starting files, dependencies, implementation boundaries, tests, exit criteria, and rollback requirements. Require the executing agent to re-read the current code and review documents, revalidate assumptions, complete authorized local work, and report any separately gated live actions. Do not authorize execution of later waves implicitly.
5. **Remaining decisions:** list only unresolved choices that materially affect delivery, with a recommended default and the evidence needed to decide.

## Review completion checklist

The review goal is complete when all of the following are true:

1. Both requested documents exist, are internally consistent, and contain the required review and planning sections.
2. The review records its baseline, coverage across all nine dimensions, evidence-backed strengths and findings, uncertainty, and material exclusions. Referenced paths, symbols, and line numbers have been checked against that baseline.
3. Safe local validation has been performed where feasible. Exact commands and results are recorded, with failed, skipped, and unavailable checks distinguished. Tests do not have to pass for the review goal to finish; failures must be explained or assigned a concrete investigation task.
4. Every finding has a disposition. Priorities are justified, dependencies have no cycles, and every wave has concrete tasks, an objective exit gate, validation, recovery guidance, milestone alignment where applicable, and a usable execution prompt.
5. The first implementation slice and any pending operator decisions are explicit. Unavailable live evidence is recorded as follow-up work and is not claimed as verified.
6. The final worktree has been compared with the initial status. Existing user work is preserved, and this review has changed only the requested documents, apart from disposable validation artifacts. No wave or live operation has been executed.
7. A final handoff links both documents and reports the results and limitations. If goal-status controls are available, mark this review goal complete only after the required work is actually finished.

Before the handoff, remove duplicate recommendations and generic filler. Repeat investigation or checks only to resolve a material inconsistency, changed evidence, or an unresolved concern. Completing this review does not authorize starting Wave 0 or creating implementation goals.

In your final response, link both documents and briefly summarize the strongest capabilities, highest-priority concerns, proposed wave sequence, validation performed, and the first recommended implementation slice. State clearly that the waves have been planned but not executed.
