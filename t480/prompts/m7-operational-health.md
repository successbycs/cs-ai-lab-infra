# M7 execution prompt — T480 operational health routine

You are operating the private T480 AI Lab from the T16 workstation. Execute M7 — T480 operational health routine proven.

## Outcome

Prove the routine can establish that the T16 can reach the T480 through the governed SSH/Windows/WSL control path and that the required Docker services are genuinely healthy. The routine is read-only: it must not start, restart, recreate, expose, or update any service.

## Safety boundaries

- Use only the fixed T480 adapter operations; do not use a free-form remote command or shell.
- Keep SSH key authentication, BatchMode, and strict host-key checking enabled.
- Do not print, copy, or record passwords, API keys, private addresses, raw database data, or unredacted logs in Git or the milestone ledger.
- PostgreSQL and n8n are required. Ollama is optional: a deliberate `SKIP` is valid when its profile is not running.
- Do not invoke `lab_services_start` just to make M7 pass. It is a separately approval-gated recovery action after a reviewed failure.

## Required execution order

1. Run the control-path check from the T16:

   ```bash
   python3 scripts/t480_adapter.py preflight
   ```

2. Run the fixed T480 health routine:

   ```bash
   python3 scripts/t480_adapter.py execute --operation lab_health
   ```

   A passing result proves Docker and Compose are available, PostgreSQL and n8n containers are healthy, PostgreSQL accepts a connection and executes a query, pgvector is installed, and the n8n host health endpoint responds. It reports Ollama as healthy only if its optional profile is running. It also reports low disk or memory as warnings.

3. If either command fails, stop the proof attempt and collect only the approved read-only diagnostic output:

   ```bash
   python3 scripts/t480_adapter.py execute --operation lab_runtime_diagnostics
   ```

   Explain the failed component and request fresh approval before any recovery action.

4. After both checks pass, record concise evidence in the ignored local milestone ledger. Refer to the command result and timestamp, but do not paste raw host output:

   ```bash
   python3 scripts/t480_milestones.py start --id M7
   python3 scripts/t480_milestones.py record-check --id M7 --check remote_control_path_verified --result pass --evidence 'T16 preflight passed; local result retained.'
   python3 scripts/t480_milestones.py record-check --id M7 --check required_lab_services_verified --result pass --evidence 'T16 lab_health passed; local result retained.'
   python3 scripts/t480_milestones.py record-check --id M7 --check ollama_state_explicit --result pass --evidence 'lab_health recorded Ollama as healthy or intentionally skipped.'
   python3 scripts/t480_milestones.py record-check --id M7 --check safe_failure_path_documented --result pass --evidence 'Reviewed read-only lab_runtime_diagnostics and approval-gated lab_services_start boundary.'
   python3 scripts/t480_milestones.py prove --id M7
   ```

## Success criteria

- The remote control path is proven by a real T16 preflight using SSH key authentication and strict host-key checking.
- A real `lab_health` run passes for Docker, PostgreSQL, pgvector, and n8n.
- The output makes the optional Ollama state explicit without requiring it to be running.
- Any remediation remains a deliberate, approval-gated decision outside the health check.
