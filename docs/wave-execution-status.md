# Wave execution status

This is an implementation and evidence index. It does not replace the raw,
local evidence required for any T480 or T16 claim.

## Wave 1 — recoverable data and schema evolution

### Completed local changes

- `docs/recovery-contract.md` inventories database state, Compose revision,
  secret-bearing recovery records, n8n volumes, raw evidence, dashboard output,
  and optional Ollama models. It distinguishes PostgreSQL-logical recovery from
  a complete lab recovery.
- `scripts/backup_manifest.py` creates and verifies a non-secret manifest for a
  PostgreSQL logical dump. `scripts/backup.sh` invokes it after a successful
  dump. Full-lab preflight names every missing artifact rather than treating a
  database dump as sufficient.
- `scripts/capture-w1-recovery-bundle.sh` defines the approved full-lab capture
  sequence: PostgreSQL dump plus labeled `n8n_data` and `n8n_files` archives,
  with opaque environment/key recovery-record IDs. The T16 pull tool verifies a
  complete full-lab bundle before retaining it. Neither command has been run
  against the T480.
- `postgres/migrations/003_migration_ledger.sql`, the matching init file, and
  `scripts/postgres_pgvector_adapter.py` record migration filenames, checksums,
  and applied times. Re-runs are no-ops, checksum drift is rejected, and a
  migration is applied in a PostgreSQL single transaction under an advisory
  lock.
- `scripts/w1-synthetic-recovery-drill.sh` and its verifier define an
  approval-gated full-stack drill with generated source/restore project names,
  isolated Docker volumes, a test-only key, and no host port publications.

### Local validation

On 2026-09-07, the local suite passed with **90 tests**. Shell syntax checks,
Python compilation, and `git diff --check` also passed. Tests cover manifest
integrity and missing artifacts; fresh, upgrade, re-run, and checksum-drift
ledger decisions; migration adapter transaction/lock behavior; and successful
and tampered synthetic evidence bundles.

### Gate status and required handoff

Wave 1 is **not complete**. The T16 target, its DPAPI recovery records, and the
non-secret local policy have been prepared. No full-lab capture, T16 bundle
transfer, Docker/database/volume recovery action, or raw recovery evidence has
been performed.

The T16 is the sole encrypted, pull-only recovery target; its controls,
limitations, and implemented transfer interface are in
`docs/t16-interim-backup-target.md`. The local policy selects a 24-hour RPO,
four-hour RTO, 30 retained daily bundles, and reviewed-model re-downloads.
On 2026-09-07, the deployed T480 environment was streamed through the governed
strict-host-key connection to create two current-user T16 DPAPI records. Their
round-trip verification succeeded, and the ignored local policy now records the
two opaque IDs and an enabled recovery-record gate. The operator still needs to
approve the isolated drill and separately approve the T480/T16 capture and
evidence sequence. The resulting evidence bundle must pass
`scripts/verify-w1-synthetic-recovery-evidence.sh` independently.

The owner-approved T16 target configuration and marker were prepared locally
on 2026-09-07. Its path is ignored and not recorded here. No T480 backup,
transfer, `.env` access, database action, or recovery drill was performed as
part of that preparation.

The ignored non-secret recovery policy was configured locally on 2026-09-07 and
was enabled only after the T16 DPAPI records were successfully created and
independently round-trip verified.

### Failure and rollback guidance

The only implementation failure was an indentation error in the migration
adapter detected by the full local test suite. It was corrected before the
successful validation above; no database or evidence artifact was affected.

A local confirmation smoke check briefly set the recovery-record gate before
the required password-manager evidence was available. It was reset immediately
to `no`; no capture, secret access, T480 action, or evidence artifact occurred.

To roll back source changes, restore the prior scripts and documentation in a
normal code review. Do not use a Git revert as recovery for a database. If the
ledger is ever applied and a migration fails, retain the failure evidence and
use a reviewed forward fix or restore a known-good backup. Leave synthetic
volumes and evidence intact until their separately approved cleanup.
