\ir /lab-postgres/migrations/003_migration_ledger.sql
INSERT INTO public.cs_ai_lab_migration_ledger (filename, sha256)
VALUES ('003_migration_ledger.sql', '506c988899a2cfbd1f71718c648d81abc2487482c6664c4fb52afe63f0946291')
ON CONFLICT (filename) DO NOTHING;
