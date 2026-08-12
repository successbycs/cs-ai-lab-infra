# M5 execution prompt — hands-off maintenance and recovery

You are operating the private T480 AI Lab from the T16 workstation. Execute M5 — hands-off maintenance and recovery proven.

## Outcome

Prove that a planned Windows restart can return the private PostgreSQL and n8n lab services without anyone logging into the T480 Windows desktop. Establish a governed Windows Update routine and prove BIOS-update readiness. This is not authority to install a BIOS update.

## Safety boundaries

- Use the fixed T480 adapter operations only; do not introduce arbitrary remote shell access.
- Do not enable Windows automatic logon or store a Windows password anywhere.
- Every restart, update installation, scheduled-task change, or firmware action requires explicit operator approval.
- Stop if PostgreSQL backup freshness, AC power, battery state, BitLocker recovery readiness, storage capacity, or current lab health is not acceptable.
- Never install BIOS/UEFI firmware alongside Windows, driver, Docker, or application updates.
- Keep n8n loopback-only and do not start optional Ollama as part of this milestone.
- Do not record credentials, recovery keys, private addresses, or raw sensitive output in Git or the milestone ledger.

## Required execution order

1. Capture a read-only maintenance preflight: Windows Update state, reboot-required state, uptime, storage, AC/battery condition, BitLocker readiness, current BIOS version, offered BIOS version and release reference, Docker, Compose, PostgreSQL, n8n, and backup freshness.
2. Show the exact boot-time scheduled-task configuration and rollback (`startup_disable`) before approval. It must run at system boot as `NT AUTHORITY\\SYSTEM`, invoke only the fixed WSL startup action, wait for Docker, and start PostgreSQL plus n8n.
3. With approval, create or update the boot-time task. Read it back and verify its trigger, principal, and action.
4. With separate approval, initiate one T16-governed Windows restart. Poll only the approved control/health surfaces until SSH, Docker, PostgreSQL, and n8n return. Do not accept task registration as proof.
5. Configure and read back a defined Windows Update maintenance window and active hours. With approval, run one quality-update cycle; if Windows reports no applicable quality update, capture that authoritative result instead. In either case, verify the lab after any required restart.
6. Capture Lenovo-supported BIOS readiness evidence. Record whether a BIOS update is available, but defer installation unless the operator separately requests it in a later maintenance window.
7. On the T480, capture a raw M5 evidence bundle and run its independent verifier. Only then record every acceptance check in the local milestone ledger and prove M5.

## Success criteria

- A boot-triggered Local System task—not a user-logon task—starts the private lab services.
- A real Windows reboot initiated from the T16 returns PostgreSQL and n8n healthy without interactive Windows logon.
- Windows quality updates are governed by a verified maintenance policy and a real cycle/no-update result has been captured.
- BIOS installation readiness is evidenced, with firmware installation deliberately deferred unless separately approved.
- The M5 raw evidence bundle passes independent verification.
