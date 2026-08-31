CREATE SCHEMA IF NOT EXISTS monitoring;

CREATE TABLE IF NOT EXISTS monitoring.healthcheck_runs (
  run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  started_at_nz text,
  finished_at timestamptz,
  finished_at_nz text,
  overall_status text NOT NULL CHECK (overall_status IN ('PASS', 'WARN', 'FAIL', 'SKIP')),
  configuration_fingerprint text,
  source text NOT NULL DEFAULT 't16_healthcheck',
  created_by text NOT NULL DEFAULT current_user
);

CREATE TABLE IF NOT EXISTS monitoring.healthcheck_checks (
  check_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id bigint NOT NULL REFERENCES monitoring.healthcheck_runs(run_id) ON DELETE CASCADE,
  check_key text NOT NULL,
  status text NOT NULL CHECK (status IN ('PASS', 'WARN', 'FAIL', 'SKIP')),
  detail text NOT NULL,
  recommended_action text NOT NULL,
  duration_ms integer CHECK (duration_ms IS NULL OR duration_ms >= 0),
  UNIQUE (run_id, check_key)
);

CREATE INDEX IF NOT EXISTS healthcheck_runs_recorded_at_idx
  ON monitoring.healthcheck_runs (recorded_at DESC);
CREATE INDEX IF NOT EXISTS healthcheck_checks_run_id_idx
  ON monitoring.healthcheck_checks (run_id);

CREATE OR REPLACE FUNCTION monitoring.record_healthcheck(payload jsonb)
RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE
  inserted_run_id bigint;
  item jsonb;
BEGIN
  INSERT INTO monitoring.healthcheck_runs (
    started_at,
    started_at_nz,
    finished_at,
    finished_at_nz,
    overall_status,
    configuration_fingerprint
  )
  VALUES (
    NULLIF(payload ->> 'started_at', '')::timestamptz,
    NULLIF(payload ->> 'started_at_nz', ''),
    NULLIF(payload ->> 'finished_at', '')::timestamptz,
    NULLIF(payload ->> 'finished_at_nz', ''),
    COALESCE(NULLIF(payload ->> 'overall_status', ''), 'FAIL'),
    NULLIF(payload ->> 'configuration_fingerprint', '')
  )
  RETURNING run_id INTO inserted_run_id;

  FOR item IN SELECT value FROM jsonb_array_elements(COALESCE(payload -> 'checks', '[]'::jsonb))
  LOOP
    INSERT INTO monitoring.healthcheck_checks (
      run_id,
      check_key,
      status,
      detail,
      recommended_action,
      duration_ms
    )
    VALUES (
      inserted_run_id,
      item ->> 'key',
      COALESCE(NULLIF(item ->> 'status', ''), 'FAIL'),
      LEFT(COALESCE(item ->> 'detail', ''), 500),
      LEFT(COALESCE(item ->> 'recommended_action', ''), 500),
      NULLIF(item ->> 'duration_ms', '')::integer
    );
  END LOOP;

  RETURN inserted_run_id;
END;
$$;

CREATE OR REPLACE FUNCTION monitoring.health_dashboard_payload()
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
  SELECT jsonb_build_object(
    'generated_at_utc', now(),
    'generated_at_nz', to_char(now() AT TIME ZONE 'Pacific/Auckland', 'YYYY-MM-DD"T"HH24:MI:SS TZ'),
    'runs', COALESCE(
      (
        SELECT jsonb_agg(
          jsonb_build_object(
            'run_id', run.run_id,
            'recorded_at_utc', run.recorded_at,
            'recorded_at_nz', to_char(run.recorded_at AT TIME ZONE 'Pacific/Auckland', 'YYYY-MM-DD"T"HH24:MI:SS TZ'),
            'started_at_utc', run.started_at,
            'started_at_nz', run.started_at_nz,
            'finished_at_utc', run.finished_at,
            'finished_at_nz', run.finished_at_nz,
            'overall_status', run.overall_status,
            'checks', COALESCE(
              (
                SELECT jsonb_agg(
                  jsonb_build_object(
                    'key', item.check_key,
                    'status', item.status,
                    'detail', item.detail,
                    'recommended_action', item.recommended_action,
                    'duration_ms', item.duration_ms
                  ) ORDER BY item.check_id
                )
                FROM monitoring.healthcheck_checks AS item
                WHERE item.run_id = run.run_id
              ),
              '[]'::jsonb
            )
          ) ORDER BY run.recorded_at DESC
        )
        FROM (
          SELECT *
          FROM monitoring.healthcheck_runs
          ORDER BY recorded_at DESC
          LIMIT 30
        ) AS run
      ),
      '[]'::jsonb
    )
  );
$$;
