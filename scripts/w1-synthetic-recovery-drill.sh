#!/usr/bin/env bash
set -euo pipefail

# Full-stack synthetic recovery drill. This is intentionally approval-gated:
# it creates only project-scoped test databases and Docker volumes, never reads
# .env, and leaves successful synthetic projects intact for inspection.

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

approve=false
test_key_file=""
while (($#)); do
  case "$1" in
    --approve) approve=true ;;
    --test-encryption-key-file)
      shift
      test_key_file="${1:-}"
      ;;
    *)
      printf 'Usage: %s --approve --test-encryption-key-file PATH\n' "$0" >&2
      exit 2
      ;;
  esac
  shift
done

[[ "$approve" == true ]] || { printf 'Refusing synthetic recovery drill without --approve after explicit operator approval.\n' >&2; exit 2; }
[[ -n "$test_key_file" && -f "$test_key_file" ]] || { printf 'A test-only encryption-key file is required.\n' >&2; exit 2; }
[[ "$(realpath "$test_key_file")" != "$root_dir/.env" ]] || { printf 'Refusing to use .env as the test encryption-key file.\n' >&2; exit 2; }
[[ -s "$test_key_file" ]] || { printf 'The test encryption-key file must not be empty.\n' >&2; exit 2; }

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
source_project="w1_source_${timestamp,,}"
restore_project="w1_restore_${timestamp,,}"
source_db="w1_source_${timestamp,,}"
restore_db="w1_restore_${timestamp,,}"
bundle_dir="${W1_EVIDENCE_DIR:-$root_dir/evidence/W1}/$timestamp"
work_dir="$(mktemp -d)"
test_env="$work_dir/recovery.env"
db_dump="$bundle_dir/postgres.sql.gz"
source_data_archive="$bundle_dir/n8n-data.tar.gz"
source_files_archive="$bundle_dir/n8n-files.tar.gz"
compose=(docker compose --env-file "$test_env" -f compose.yaml -f postgres/recovery/w1-isolated-compose.yaml)
n8n_image="n8nio/n8n:1.123.76@sha256:66b6bfd6716877591d9c21340250f44f842e6b03f97ccaed09b9f95e13cf5331"

cleanup_sensitive_files() {
  rm -rf "$work_dir"
}
trap cleanup_sensitive_files EXIT

umask 077
test_password="$(openssl rand -hex 24)"
test_key="$(tr -d '\r\n' < "$test_key_file")"
[[ -n "$test_key" ]] || { printf 'The test-only encryption key resolves to empty.\n' >&2; exit 2; }
cat > "$test_env" <<EOF
POSTGRES_DB=$source_db
POSTGRES_USER=w1_recovery
POSTGRES_PASSWORD=$test_password
N8N_ENCRYPTION_KEY=$test_key
TZ=Pacific/Auckland
N8N_HOST=localhost
N8N_PROTOCOL=http
N8N_PORT=5678
N8N_BIND_ADDRESS=127.0.0.1
N8N_DIAGNOSTICS_ENABLED=false
N8N_PERSONALIZATION_ENABLED=false
N8N_RUNNERS_ENABLED=true
NODE_FUNCTION_ALLOW_BUILTIN=crypto
HEALTH_DASHBOARD_BIND_ADDRESS=127.0.0.1
HEALTH_DASHBOARD_PORT=18080
EOF
unset test_key test_password

mkdir -p "$bundle_dir"
status=0
probe() {
  local id="$1"
  shift
  local output="$bundle_dir/${id}.txt"
  local exit_code=0
  { printf 'probe: %s\nstarted_at: %s\n' "$id" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"; "$@"; } >"$output" 2>&1 || exit_code=$?
  printf 'finished_at: %s\nexit_code: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$exit_code" >>"$output"
  (( exit_code == 0 )) || status=1
}

wait_for_service() {
  local project="$1" service="$2"
  shift 2
  for _attempt in $(seq 1 45); do
    "${compose[@]}" --project-name "$project" exec -T "$service" "$@" >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}

# All project names, databases, and volumes are generated above. Do not replace
# them with active Compose names or POSTGRES_DB values from a live environment.
probe source_start "${compose[@]}" --project-name "$source_project" up -d postgres n8n_files_init n8n
probe source_health wait_for_service "$source_project" n8n wget -q --spider http://localhost:5678/healthz
probe source_synthetic_file "${compose[@]}" --project-name "$source_project" exec -T n8n sh -c 'printf synthetic-recovery > /home/node/.n8n-files/w1-synthetic.txt'
probe source_dump bash -c 'docker compose --env-file "$1" -f compose.yaml -f postgres/recovery/w1-isolated-compose.yaml --project-name "$2" exec -T postgres pg_dump --clean --if-exists -U w1_recovery -d "$3" | gzip -9 > "$4"' _ "$test_env" "$source_project" "$source_db" "$db_dump"
probe archive_n8n_data docker run --rm --entrypoint /bin/sh -v "${source_project}_n8n_data:/source:ro" -v "$bundle_dir:/backup" "$n8n_image" -c 'tar -C /source -czf /backup/n8n-data.tar.gz .'
probe archive_n8n_files docker run --rm --entrypoint /bin/sh -v "${source_project}_n8n_files:/source:ro" -v "$bundle_dir:/backup" "$n8n_image" -c 'tar -C /source -czf /backup/n8n-files.tar.gz .'

# Reuse only the test key and test password in a second isolated project. Its
# database name changes before startup, so a restore can never connect to the
# source or an active lab database.
sed -i "s/^POSTGRES_DB=.*/POSTGRES_DB=$restore_db/" "$test_env"
probe restore_postgres_start "${compose[@]}" --project-name "$restore_project" up -d postgres
probe restore_postgres_ready wait_for_service "$restore_project" postgres pg_isready -U w1_recovery -d "$restore_db"
probe restore_database bash -c 'gunzip -c "$1" | docker compose --env-file "$2" -f compose.yaml -f postgres/recovery/w1-isolated-compose.yaml --project-name "$3" exec -T postgres psql -v ON_ERROR_STOP=1 -U w1_recovery -d "$4"' _ "$db_dump" "$test_env" "$restore_project" "$restore_db"
probe restore_n8n_data docker run --rm --user 0:0 --entrypoint /bin/sh -v "${restore_project}_n8n_data:/target" -v "$bundle_dir:/backup:ro" "$n8n_image" -c 'tar -C /target -xzf /backup/n8n-data.tar.gz && chown -R 1000:1000 /target'
probe restore_n8n_files docker run --rm --user 0:0 --entrypoint /bin/sh -v "${restore_project}_n8n_files:/target" -v "$bundle_dir:/backup:ro" "$n8n_image" -c 'tar -C /target -xzf /backup/n8n-files.tar.gz && chown -R 1000:1000 /target'
probe restored_n8n_start "${compose[@]}" --project-name "$restore_project" up -d n8n
probe restored_n8n_health wait_for_service "$restore_project" n8n wget -q --spider http://localhost:5678/healthz

{
  printf 'schema_version=cs-ai-lab.w1-synthetic-recovery.v1\n'
  printf 'captured_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'source_project=%s\nrestore_project=%s\n' "$source_project" "$restore_project"
  printf 'source_database=%s\nrestore_database=%s\n' "$source_db" "$restore_db"
  printf 'encryption_key=test-only-preserved-not-recorded\n'
  printf 'artifacts=postgres.sql.gz,n8n-data.tar.gz,n8n-files.tar.gz\n'
  printf 'git_revision=%s\n' "$(git rev-parse HEAD)"
} > "$bundle_dir/manifest.txt"
(cd "$bundle_dir" && sha256sum manifest.txt source_start.txt source_health.txt source_synthetic_file.txt source_dump.txt archive_n8n_data.txt archive_n8n_files.txt restore_postgres_start.txt restore_postgres_ready.txt restore_database.txt restore_n8n_data.txt restore_n8n_files.txt restored_n8n_start.txt restored_n8n_health.txt postgres.sql.gz n8n-data.tar.gz n8n-files.tar.gz > SHA256SUMS)

printf 'Wave 1 synthetic recovery evidence: %s\n' "$bundle_dir"
printf 'Verify it with: ./scripts/verify-w1-synthetic-recovery-evidence.sh %q\n' "$bundle_dir"
printf 'Synthetic projects retained for inspection: %s and %s\n' "$source_project" "$restore_project"
printf 'Cleanup is a separate approved destructive action.\n'
exit "$status"
