---
name: backup-and-restore
description: Create, verify, review, or safely rehearse recovery of this lab's PostgreSQL and recovery bundles.
---

# Backup and restore

Use for backup, restore, recovery evidence, retention, or disaster-recovery
requests. Read [backup and restore](../../../docs/backup-restore.md) and
[the recovery contract](../../../docs/recovery-contract.md) before acting.

- Treat a logical PostgreSQL dump as database recovery only; it does not prove
  recovery of `.env`, n8n encryption keys, n8n volumes, dashboard output, or
  Ollama models.
- Verify manifests with `scripts/backup_manifest.py verify` before relying on a
  captured backup. Keep dumps, manifests, and evidence out of Git.
- A restore changes data. Identify the exact target database and backup, stop
  writers, and obtain explicit authorization before any live restore.
- Use the isolated M3 drill only to validate PostgreSQL-logical recovery; it
  must never target `POSTGRES_DB` or a live application database. Use the
  separate Wave 1 full-stack drill for claims involving n8n volumes and the
  protected encryption-key/configuration recovery path.
- When [backup pause](../../../BACKUPS-PAUSED.md) is active, do not create a
  backup, recovery bundle, or drill artifact. Read-only manifest verification
  remains permitted.
- Do not delete backups, evidence, test databases, or volumes as incidental
  cleanup. Those are separate, explicitly authorized actions.

Report the backup identity, manifest-verification result, scope limitations,
and whether the operation was isolated or live—without exposing contents.
