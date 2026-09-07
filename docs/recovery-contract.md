# Full-lab recovery contract

Status: design baseline. This document does not prove a backup, an off-host
copy, or a restore. Those claims require the separately approved Wave 1 drill
and its raw local evidence bundle.

## Owner decisions required before a recoverable backup is declared

The owner must record the following in a protected decision record that does
not expose its destination, credentials, recovery key, or physical location in
Git:

1. The protected copy method and its encryption and physical-access model. The
   T16 is the sole approved target, as documented in [the T16 target
   runbook](t16-interim-backup-target.md). This accepts the risk that a shared
   site or T16 failure removes the separate recovery copy.
2. Recovery-point objective (RPO), recovery-time objective (RTO), and the
   retention period. The approved initial policy is a 24-hour RPO, a four-hour
   RTO, and 30 retained daily T16 bundles.
3. The protected recovery method for `N8N_ENCRYPTION_KEY`: a T16-local,
   current-user Windows DPAPI record on the prepared encrypted target. The
   environment is protected the same way. The record values are never written
   to Git or the backup manifest.
4. Whether Ollama model artifacts are copied or intentionally re-downloaded.
   The approved initial disposition is to re-download reviewed models.

Create and independently round-trip verify the two T16 DPAPI records with:

```bash
python3 scripts/create-w1-dpapi-recovery-records.py --from-t480 --approve
```

The command reads the deployed T480 `.env` only after approval through the
existing strict-host-key connection, emits no secret value,
and opens the capture gate only after both records decrypt for the current T16
Windows user.

Until those decisions exist, `backup.sh` produces a **PostgreSQL-logical**
backup only. It must not be described as a full-lab backup.

## Recovery inventory

| State | Classification | PostgreSQL dump restores? | Recovery method and evidence |
| --- | --- | --- | --- |
| Application PostgreSQL data, including n8n database state | Required | Yes, for the selected database at capture time | Compressed logical dump plus its non-secret manifest and SHA-256 verification. |
| PostgreSQL image and Compose revision | Required | No | The manifest records the reviewed Git and Compose revisions; restore uses a reviewed compatible revision. |
| Environment configuration | Required, secret-bearing | No | Recover from the protected owner-controlled secret record. The manifest may identify a recovery record by opaque identifier only; it never contains `.env` or a secret value. |
| `N8N_ENCRYPTION_KEY` | Required, secret-bearing | No | Recover the exact protected key through the owner-approved method before starting n8n. A different key can make stored credentials unusable. |
| `n8n_data` volume | Required | No | Restore a captured, integrity-checked volume archive into an isolated volume; never mount a live volume during a drill. |
| `n8n_files` volume | Required when workflows rely on local files | No | Restore its captured, integrity-checked archive into an isolated volume. |
| Raw operational evidence | Required only for its stated milestone | No | Keep local under the evidence policy; retain the verifier and hashes. It is not application state. |
| Dashboard static output | Reconstructable | No | Regenerate from redacted monitoring data after the dashboard code is restored. |
| Ollama models | Owner decision | No | Either verify the captured model artifact or re-download the reviewed model. The decision is recorded outside Git. |

## Manifest contract

`scripts/backup_manifest.py` creates and verifies a non-secret, versioned
manifest. A PostgreSQL-logical manifest contains the dump hash, capture time,
Git revision, Compose-file hash, and a declared limited scope. Its verifier
can also require the full-lab artifact set; that preflight fails clearly until
the protected environment/key and n8n-volume recovery records have been
supplied.

A manifest contains identifiers and hashes only. It must not contain database
passwords, encryption keys, off-host destinations, host paths, customer data,
or raw evidence.

## Safe recovery sequence

1. Review the manifest, its verifier output, the approved recovery scope, and
   the protected key/configuration recovery record.
2. Restore into newly named test databases and project-scoped test volumes.
   Do not target the active Compose project, `POSTGRES_DB`, `n8n_data`, or
   `n8n_files`.
3. Supply the preserved test-only encryption key through an ephemeral test
   environment file. Start n8n only in the isolated project and capture its
   health result.
4. Retain the isolated test data and raw evidence until a separately approved
   cleanup. If any step fails, stop, preserve the error and manifest, and use
   a reviewed forward fix or restore the known-good backup. Do not mark a
   migration applied manually and do not use Git revert as database recovery.

The existing M3 drill remains a PostgreSQL-only synthetic proof. Wave 1's
full-stack drill is a separate proof label and cannot upgrade M3's claim.

`scripts/w1-synthetic-recovery-drill.sh` implements that separate drill. It
requires `--approve` and an explicit test-only encryption-key file, creates
only generated `w1_source_*` and `w1_restore_*` Compose projects, removes host
port publications through `postgres/recovery/w1-isolated-compose.yaml`, and
retains its synthetic data for review. It has not been run by this repository
change.
