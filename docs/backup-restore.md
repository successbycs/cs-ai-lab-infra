# Backup and restore

`./scripts/backup.sh` creates a compressed, timestamped logical PostgreSQL dump on the host at `postgres/backup/`. It runs `pg_dump` in the database container but redirects the result outside it, so the backup survives container recreation. Backup files are ignored by Git; copy tested backups to storage outside the T480.

To restore into a deliberately selected running lab database, first stop application writers, identify the exact backup, and run:

```bash
gunzip -c postgres/backup/<file>.sql.gz | docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

Load `.env` into your shell first if its variables are not already set, or substitute the intended database user and name. Restoring overwrites data where the dump contains destructive SQL; practise using synthetic data before trusting this procedure. A stronger future setup should automate off-host retention and restore testing.
