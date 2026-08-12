# PostgreSQL and pgvector adapter

`scripts/postgres_pgvector_adapter.py` adapts the Autonomous Framework Supabase adapter's capability diagnostics and approval model to this repository's private Docker PostgreSQL service.

It does not use Supabase, expose PostgreSQL, accept raw SQL, or copy database credentials to the T16. Commands route through the proven T16-to-T480 bridge and execute `psql` inside the PostgreSQL container.

After M2 is running, use the read-only operations first:

```bash
python3 scripts/postgres_pgvector_adapter.py preflight
python3 scripts/postgres_pgvector_adapter.py inspect
python3 scripts/postgres_pgvector_adapter.py vector-probe
```

Schema changes must be reviewed `.sql` files in `postgres/migrations/` and require approval. Before applying one, the adapter confirms the T480's deployed file has the same SHA-256 hash as the reviewed local file, then streams that file to `psql` inside the container:

```bash
python3 scripts/postgres_pgvector_adapter.py apply-migration --migration-file 001_example.sql --approve
```

Real proof remains a T480-captured evidence bundle showing the query results and service state; the adapter audit log is metadata only.
