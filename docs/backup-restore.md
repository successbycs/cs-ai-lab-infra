# Backup and restore

`./scripts/backup.sh` creates a compressed, timestamped logical PostgreSQL dump on the host at `postgres/backup/`, with a non-secret JSON manifest beside it. It runs `pg_dump` in the database container but redirects the result outside it, so the backup survives container recreation. The manifest records the dump SHA-256, capture time, Git revision, Compose-file hash, and its deliberately limited recovery scope. Backup files and manifests are ignored by Git.

Verify a captured logical backup without contacting Docker:

```bash
python3 scripts/backup_manifest.py verify postgres/backup/<file>.manifest.json
```

This is a PostgreSQL-logical backup, not a full-lab recovery claim. It cannot
restore `.env`, the n8n encryption key, `n8n_data`, `n8n_files`, dashboard
output, or Ollama models. The full inventory and owner decisions are in
[the recovery contract](recovery-contract.md). The full-lab preflight is
expected to fail until the required protected recovery records exist:

```bash
python3 scripts/backup_manifest.py verify postgres/backup/<file>.manifest.json --require-full-lab
```

## Full-lab capture for the prepared T16 target

`scripts/capture-w1-recovery-bundle.sh` captures the PostgreSQL dump plus
`n8n_data` and `n8n_files` archives into one local bundle and builds a
full-lab manifest. It requires the ignored `.w1-recovery.local` file, based on
`w1/recovery-records.local.example`, to contain opaque identifiers for the
protected environment and n8n-key recovery records. It never accepts or copies
the secret values themselves.

The command requires explicit approval and a prior operator confirmation that
n8n writes are quiesced. It does not transfer the result; the prepared T16
target remains the only approved transfer destination.

To restore into a deliberately selected running lab database, first stop application writers, identify the exact backup, and run:

```bash
gunzip -c postgres/backup/<file>.sql.gz | docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

Load `.env` into your shell first if its variables are not already set, or substitute the intended database user and name. Restoring overwrites data where the dump contains destructive SQL; practise using synthetic data before trusting this procedure. A stronger future setup should automate off-host retention and restore testing.

## M3 recovery proof

`./scripts/m3-recovery-proof.sh` is a deliberately isolated restore drill. It creates a timestamped synthetic source database and a separate synthetic restore database; it never targets `POSTGRES_DB`, the live n8n database. It writes a compressed source backup to `postgres/backup/` and captures non-secret raw results to `evidence/M3/<UTC-timestamp>/`.

Run the script and then its printed verifier directly on the T480. The verifier checks bundle and backup hashes plus the exact synthetic data result after restore. Retain the resulting databases and backup until a separately approved cleanup.
