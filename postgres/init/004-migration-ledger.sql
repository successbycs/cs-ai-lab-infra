\ir /lab-postgres/migrations/003_migration_ledger.sql
INSERT INTO public.cs_ai_lab_migration_ledger (filename, sha256)
VALUES ('003_migration_ledger.sql', '59e0c9a9181ee145c745b00eb2fa801819cd20eca14f711474722badf5c21dab')
ON CONFLICT (filename) DO NOTHING;
