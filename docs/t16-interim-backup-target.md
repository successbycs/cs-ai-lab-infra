# T16 interim backup target

The T16 is the approved **sole backup target** for this lab. It receives an
encrypted recovery copy from the T480 only after the per-copy approval and
preflight described below. It is a separate machine and helps protect against
T480 disk failure, but it is not an off-site copy if both devices share the
same building or network. The owner accepts this interim risk; no cloud or
other off-site target is part of this recovery method.

## Target controls

- Use a dedicated T16 backup volume protected by device or volume encryption.
  Keep environment and n8n-key recovery material as current-user Windows DPAPI
  records on that prepared encrypted target, never on the T480 or in Git.
- The T16 initiates a pull from the T480 using the existing strict-host-key,
  key-authenticated control path. Do not mount the T16 target on the T480 and
  do not place T16 backup credentials on the T480.
- Store the copy in a T16-local path configured outside Git. The copy contains
  only the approved recovery bundle and its manifest; it must not contain a
  plaintext `.env`, `N8N_ENCRYPTION_KEY`, or raw customer content.
- Preserve version history on the T16. Do not overwrite the last independently
  verified copy.

## Implemented T16 pull interface

After confirming that the chosen T16 volume is encrypted, prepare it in one
command. This writes the ignored repository-root `.t16-backup.local` file and
the target marker; it refuses to overwrite an existing local configuration:

```bash
python3 scripts/t16_backup_pull.py prepare-target \
  --target-dir 'D:\CS-AI-Lab-Backups' \
  --confirm-encrypted-volume \
  --approve
```

Use the actual encrypted-volume path in place of the example. The template at
`t16/backup-target.local.example` remains available for a manually managed
configuration.

After `scripts/backup.sh` has created a named T480 PostgreSQL dump and manifest,
pull that exact basename from the T16:

```bash
python3 scripts/t16_backup_pull.py pull --backup-name cs_ai_lab-YYYYMMDDThhmmss+ZZZZ.sql.gz --approve
```

The interface accepts only a timestamped PostgreSQL dump basename, retrieves
only that dump and its derived manifest through `scp.exe` with batch mode and
strict host-key checking, verifies the copied manifest before retention, and
refuses overwrites. It does not access `.env`, n8n encryption keys, raw
evidence, or arbitrary remote paths.

For a separately approved full-lab bundle created by
`scripts/capture-w1-recovery-bundle.sh`, pull its exact bundle identifier:

```bash
python3 scripts/t16_backup_pull.py pull-full-lab \
  --bundle-id w1-YYYYMMDDThhmmssZ \
  --approve
```

This copies only the fixed full-lab manifest and three archives and retains them
only after `manifest.json` verifies its PostgreSQL and both n8n volume archives
plus the required opaque recovery-record identifiers.

Because the source bundle lives in T480 WSL while the pull endpoint is Windows
OpenSSH, the pull creates a fixed, short-lived Windows-visible staging copy of
that exact bundle. The transfer uses SFTP `reget` for the three fixed archives
and refreshes the manifest on every attempt. Incoming files and source staging are preserved on
network failure so the same bundle ID can resume. After successful local hash
verification, the T16 retains the bundle and source staging is removed. A
cleanup failure is reported separately and cannot discard a verified T16 copy.
The T16 remains the only retained backup target.

## Per-copy preflight and evidence

Before an approved transfer, verify the T16 volume is encrypted, unlocked for
the operator, has enough free capacity for the selected bundle plus one prior
version, and has a tested recovery-key path. On the T480, create and verify
the manifest first. On the T16, pull the selected bundle, verify hashes against
the manifest, and record only the bundle identifier, manifest hash, result,
and timestamp in local evidence. Do not record paths, addresses, credentials,
or secret values.

The T16 copy is not proof of a restore. Wave 1 remains incomplete until the
protected n8n-key recovery method, RPO/RTO and retention, Ollama disposition,
isolated synthetic recovery drill, and independently verified evidence are all
complete.

## Recovery and replacement

If the T16 is lost or its encrypted volume cannot be unlocked, the lab has no
separate recovery copy. Rebuild it from reviewed source and accept loss of
state rather than weakening T480 access controls. Do not delete any verified
T16 bundle until a reviewed replacement policy is in force.
