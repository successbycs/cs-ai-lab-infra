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
  complete full-lab bundle before retaining it. The T480 bundle `w1-20260907T060119Z` was captured and verified;
  earlier T16 transfers failed without retaining a verified copy.
- `postgres/migrations/003_migration_ledger.sql`, the matching init file, and
  `scripts/postgres_pgvector_adapter.py` record migration filenames, checksums,
  and applied times. Re-runs are no-ops, checksum drift is rejected, and a
  migration is applied in a PostgreSQL single transaction under an advisory
  lock.
- `scripts/w1-synthetic-recovery-drill.sh` and its verifier define an
  approval-gated full-stack drill with generated source/restore project names,
  isolated Docker volumes, a test-only key, and no host port publications.

### Local validation

On 2026-09-07, the local suite passed with **102 tests**. Shell syntax checks,
Python compilation, and `git diff --check` also passed. Tests cover manifest
integrity and missing artifacts; fresh, upgrade, re-run, and checksum-drift
ledger decisions; migration adapter transaction/lock behavior; and successful
and tampered synthetic evidence bundles.

### Gate status and required handoff

Wave 1 is **not complete**. The T16 target, its DPAPI recovery records, and the
non-secret local policy have been prepared. An approved full-lab capture and
several isolated synthetic recovery attempts have run. Synthetic recovery
evidence `20260907T081250Z` passed verification on T480 and, after copying all
22 evidence files, independently on T16. Completion still requires a verified
retained full-lab T16 bundle.

The T16 is the sole encrypted, pull-only recovery target; its controls,
limitations, and implemented transfer interface are in
`docs/t16-interim-backup-target.md`. The local policy selects a 24-hour RPO,
four-hour RTO, 30 retained daily bundles, and reviewed-model re-downloads.
On 2026-09-07, the deployed T480 environment was streamed through the governed
strict-host-key connection to create two current-user T16 DPAPI records. Their
round-trip verification succeeded, and the ignored local policy now records the
two opaque IDs and an enabled recovery-record gate. The owner subsequently authorized the drill, capture, transfer, and scoped
repairs. The resulting evidence bundle must pass
`scripts/verify-w1-synthetic-recovery-evidence.sh` independently.

The owner-approved T16 target configuration and marker were prepared locally
on 2026-09-07. Its path is ignored and not recorded here. No T480 backup,
transfer, `.env` access, database action, or recovery drill was performed as
part of that preparation.

The ignored non-secret recovery policy was configured locally on 2026-09-07 and
was enabled only after the T16 DPAPI records were successfully created and
independently round-trip verified.

### Failure and rollback guidance

Earlier validation caught a migration-adapter indentation error. Live attempts
also exposed missing executable modes, archive ownership errors, schema
collisions, and unreliable transport behavior. These were repaired in scoped
commits.

The transport now runs scripts with child standard input isolated and propagates
exit codes through Windows SSH and WSL. A live test printed both sides of an
input-consuming command and correctly returned exit 7. The recovery drill uses
pipefail, stops at its first failed probe, quiesces its source n8n before
capture, and verifies restored database/file markers. Version 2 evidence
requires complete checksum coverage; version 1 fixtures remain verifiable.

Further live diagnostics found repeated WSL shutdowns and a malformed Windows
boot-task command. The corrected launcher preserves the complete Bash command,
waits for the WSL process, and reports its exit code. Its PowerShell quoting is
covered by an executable regression test. The corrected boot task was installed
and observed running, with a WSL keepalive process present. The live PostgreSQL,
n8n, dashboard, and Ollama containers subsequently reported healthy. Eighteen
older generated synthetic containers were stopped while preserving their
volumes and evidence; new drills stop their own test containers on exit.

The next synthetic attempt, `20260907T080304Z`, exposed a separate fresh-init
failure: the migration ledger's SQL filename constraint rejected valid migration
names. Migration 003 and its initialization checksum were corrected in
`7519f3d`; the live database had no ledger table when checked. After connectivity
returned, the change was deployed and fresh initialization and database restore
passed. That attempt then exposed Docker address-pool exhaustion from earlier
test networks. Twenty-six unused, labeled networks belonging to recorded test
attempts were removed while preserving volumes and evidence. Commit `5044357`
releases each drill's unused networks on exit and removes network access from
its directory-initialization helper. It was deployed before the successful
`20260907T081250Z` drill.

The full-lab transfer now resumes fixed artifacts through Windows SFTP with
strict host-key checking and keepalives. Failed transfers retain incoming bytes
and source staging for retry. Only fully hash-verified bundles become retained
backups. Source staging cleanup is checked separately from backup validity.

Incoming PostgreSQL data for `w1-20260907T060119Z` resumed from 36,203,520 bytes
and was observed beyond 237 MB of 3,636,612,802 bytes. SSH connection timeouts
remain intermittent; the boot task remained running during subsequent checks.
The latest full-lab transfer is still running at this status update. No full-lab
T16 copy has yet passed verification. If the transfer fails, inspect its lock
and repeat the same bundle ID after the active process exits. Full artifact
hash verification and retention remain completion gates.

A local confirmation smoke check briefly set the recovery-record gate before
the required password-manager evidence was available. It was reset immediately
to `no`; no capture, secret access, T480 action, or evidence artifact occurred.

To roll back source changes, restore the prior scripts and documentation in a
normal code review. Do not use a Git revert as recovery for a database. If the
ledger is ever applied and a migration fails, retain the failure evidence and
use a reviewed forward fix or restore a known-good backup. Leave synthetic
volumes and evidence intact until their separately approved cleanup.
