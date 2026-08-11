# M3 execution prompt — recovery proof

## Objective

Prove a complete PostgreSQL backup-and-restore path on the T480 lab using disposable synthetic data. The proof must be captured on the T480 and independently verified from its raw evidence bundle.

M0, M1, and M2 are proven prerequisites. The milestone ledger is only an index; it is not proof.

## Absolute safety boundary

- Never read, write, dump, restore, stop, or replace the live n8n application database identified by `POSTGRES_DB`.
- Create two new uniquely named synthetic databases: one source and one restore target.
- Create the compressed backup on the T480 host in ignored `postgres/backup/`, outside the PostgreSQL container.
- Keep the synthetic databases and backup after success for inspection. Cleanup is a separate, explicit destructive action.
- Do not print `.env`, database passwords, API keys, or n8n data.

## Execution phases

1. Read-only preflight: confirm the repository, `.env`, PostgreSQL container, Docker Compose, free storage, and pgvector availability. Stop on failure.
2. Explain the exact M3 mutations and obtain fresh approval immediately before creating the synthetic databases.
3. Run `./scripts/m3-recovery-proof.sh` directly on the T480 from the repository root.
4. The script must create known synthetic rows (`alpha`, `beta`, `gamma` with pgvector embeddings), dump only the synthetic source database, restore into the distinct synthetic restore database, and query both databases.
5. Run the printed `./scripts/verify-m3-recovery-evidence.sh evidence/M3/<timestamp>` command directly on the T480. The verifier checks hashes and exact source/restore results without contacting live services.
6. Record the verified bundle path and the operator-observed verifier result in the local milestone ledger, then prove M3 only after all registry checks pass.

## Acceptance proof

M3 is successful only when the raw bundle contains successful source creation, synthetic seed, host-side compressed backup, distinct restore creation, restore, and identical source/restored result:

`3|alpha,beta,gamma|3.000000`

The operator must see the verifier output on the T480. A JSON record alone cannot establish M3 success.
