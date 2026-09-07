-- The ledger makes reviewed infrastructure migrations identifiable after the
-- existing monitoring schema has been installed. Do not edit an applied file:
-- the governed adapter compares this SHA-256 record before every application.
CREATE TABLE IF NOT EXISTS public.cs_ai_lab_migration_ledger (
  filename text PRIMARY KEY CHECK (filename ~ '^[A-Za-z0-9][A-Za-z0-9_.-]*\\.sql$'),
  sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  applied_at timestamptz NOT NULL DEFAULT now()
);

DO $$
DECLARE
  existing_sha256 text;
BEGIN
  SELECT sha256 INTO existing_sha256
  FROM public.cs_ai_lab_migration_ledger
  WHERE filename = '001_health_dashboard.sql';
  IF existing_sha256 IS NOT NULL
     AND existing_sha256 <> '988e79444923afa86d0f0b71c8ee52cbc9b80ea7a6c8280b17fc5971f4dc58ca' THEN
    RAISE EXCEPTION 'checksum drift for 001_health_dashboard.sql';
  END IF;

  SELECT sha256 INTO existing_sha256
  FROM public.cs_ai_lab_migration_ledger
  WHERE filename = '002_healthcheck_lifecycle.sql';
  IF existing_sha256 IS NOT NULL
     AND existing_sha256 <> '7494e8375bf5ee7a0094fb25dcc078be18448cd54fb5858d7bc894052c8c3035' THEN
    RAISE EXCEPTION 'checksum drift for 002_healthcheck_lifecycle.sql';
  END IF;
END;
$$;

INSERT INTO public.cs_ai_lab_migration_ledger (filename, sha256)
VALUES
  ('001_health_dashboard.sql', '988e79444923afa86d0f0b71c8ee52cbc9b80ea7a6c8280b17fc5971f4dc58ca'),
  ('002_healthcheck_lifecycle.sql', '7494e8375bf5ee7a0094fb25dcc078be18448cd54fb5858d7bc894052c8c3035')
ON CONFLICT (filename) DO NOTHING;
