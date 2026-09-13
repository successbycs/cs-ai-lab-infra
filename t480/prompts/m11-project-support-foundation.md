# M11 — project-support foundation (operator prompt)

Build the smallest reusable project-support foundation for my T480 lab.
I use this for my own MVPs and pilots, not enterprise infrastructure.

Terra does implementation, tests and operational documentation. Use Astra for
architecture review, difficult fixes and technical approval of any rollout.
Inspect the repo's AGENTS.md, current architecture, operation catalog, evidence
and deployed state before editing. Preserve existing changes and deployments.

Important context:
- Penpot WITH MCP is already deployed. Keep it operational and retain the existing private access route, shared design ownership and service boundaries.
- Pt Chev website production remains on Vercel/Supabase. It does not wait for this lab work. Do not move it, deploy it on T480 or change its Google publisher.
- Every product owns its own source, tests, assets and deployment definition. This repo owns host operations, reusable templates and deployment inventory.
- The LLM router was recently disabled in the accessible controller environment because it slowed VS Code. Verify host identity if inspecting router status. Do not restart a router or redirect Codex/Claude/VS Code traffic as a side effect.

## Milestone 1 — establish facts and capacity

Use existing governed read-only operations against the actual T480. Distinguish controller/T16 resources from T480 resources. Inventory live stacks, versions, ports, networks, storage and resource use without printing secrets or raw data. Verify physical Windows disk free space AND the storage hosting each WSL/Docker virtual disk; virtual Linux free space is not physical capacity. Recheck the previously reported 17.7 GiB free on C: and 16 GiB RAM; they are historical reports, not fresh measurements. Inspect RAM module count/speed and installed SSD model if supported by a scoped read operation. Record sustained use/headroom rather than infer capacity from a single CPU sample or configured container limits. Recommend precise compatible storage/RAM next steps after identification. No cleanup, volume deletion, disk migration or purchases in this milestone.

## Milestone 2 — reusable project contract and template

Implement a small project registry/example schema with: owner, repository, revision/image, service/health URL, exposure, secrets-file reference (no values), storage/backup needs, resource estimate, update and rollback instructions. Implement and validate a minimal standalone static-web Compose template with unique Compose project naming, health check, restart policy, log rotation and private networking. Include configurable CPU/memory/PID limits sized from measured headroom and validated under representative use. No database or persistent volume unless the project needs it. No port publication by default; optional private ingress is explicitly configured. Prefer Compose-generated scoped names over globally fixed container_name values. Include lifecycle commands for one explicitly named project; no commands that stop/rebuild the entire lab or accept arbitrary unvalidated remote shell input. Add an undeployed example product. Pt Chev may be documented as externally hosted, not installed or migrated by this task.

## Milestone 3 — practical access, assets and testing conventions

Document project-owned design exports, source assets, generated output and licence records. Avoid a global mutable asset volume shared across unrelated projects. Document temporary Expo Metro sessions and their exact private device-access requirements; Expo is selected for future phone/tablet testing but is not an always-on lab service. No Expo/game/Blender application implementation here. If a real first private project needs ingress, prepare one minimal Caddy proposal with routes, health checks and rollback. Frontend services must share its routing network to be reachable; databases stay on separate project networks. A Docker network or 0.0.0.0 binding does not prove firewall protection or actual reachability. Do not deploy ingress or change firewall/DNS/tailnet exposure under this prompt.

## Milestone 4 — operational and secret-storage follow-up

Extend existing lightweight health/capacity and backup inventory where needed; do not add a parallel monitoring platform. Document per-project recoverable state, off-device copies and a scoped restore-test approach. Existing live backup/restore actions follow the repo's approved operations and mutation boundaries. Assess whether the deployed OpenWorker actually offers suitable secret storage. Record capability, runtime injection, backup, rotation/revocation and rollback. Use protected ignored configuration for the interim; no shared .env across products. Record the prior Penpot-key exposure as requiring rotation evidence, without printing, copying or automatically regenerating keys. Prepare any credential migration as a concrete separate operation; do not invent store capabilities.

## Milestone 5 — verification, Astra review and handoff

Run relevant repo tests, template/Compose validation with dummy values, link and diff checks. Demonstrate independent lifecycle and rollback using local isolated synthetic tests where possible. Do not label local tests as T480 deployment proof. Astra reviews the resulting diff, operation boundaries, capacity evidence and whether each addition earns its complexity. Fix findings and retest affected work. Return exact changed files, tests, remaining gaps, resource budget, and a concrete first-live-rollout proposal with commands/targets, access changes and rollback.

Authority and stop boundaries: this task authorises local repo implementation, tests and governed read-only T480 inspection. New live services, restarts, firewall/exposure changes, credentials, disk cleanup/moves, purchases and product migrations need an explicitly approved rollout scope. Do all useful preparation before asking for that decision. If an existing explicit approval already covers the exact operation, cite it rather than asking twice. Do not claim this prompt itself deployed anything.

No Kubernetes, SSO, local registry, monitoring suite, GPU/rendering service, additional database, always-on Expo service or automatic model routing by default. Reuse installed capabilities. If blocked, record evidence, affected milestone, owner and exact next action; continue independent work without repeated prompts.

Completion: verified actual-host inventory, tested reusable templates/contract, operational and secrets follow-up, Astra assessment and a reviewable minimal live-rollout proposal. The lab and all existing project deployments remain independently operable. Report any unverified host access honestly.
