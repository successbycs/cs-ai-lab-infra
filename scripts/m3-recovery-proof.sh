#!/usr/bin/env bash
set -euo pipefail

# Run manually on the T480 from the repository root, after explicit M3 approval.
# This deliberately never reads from, writes to, backs up, or restores the live
# application database named by POSTGRES_DB.

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

[[ -f .env ]] || { printf 'Refusing M3 recovery proof: .env is missing.\n' >&2; exit 1; }
set -a
# shellcheck disable=SC1091
source .env
set +a

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
safe_timestamp="${timestamp,,}"
source_db="m3_source_${safe_timestamp}"
restore_db="m3_restore_${safe_timestamp}"
backup_dir="$root_dir/postgres/backup"
backup_file="$backup_dir/${source_db}.sql.gz"
bundle_dir="${M3_EVIDENCE_DIR:-$root_dir/evidence/M3}/$timestamp"
expected_row='3|alpha,beta,gamma|3.000000'

mkdir -p "$backup_dir" "$bundle_dir"

status=0
run_probe() {
  local id="$1"
  shift
  local output_file="$bundle_dir/${id}.txt"
  local started_at finished_at exit_code=0
  started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  {
    printf 'probe: %s\nstarted_at: %s\n' "$id" "$started_at"
    "$@"
  } >"$output_file" 2>&1 || exit_code=$?
  finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'finished_at: %s\nexit_code: %s\n' "$finished_at" "$exit_code" >>"$output_file"
  if (( exit_code != 0 )); then
    status=1
  fi
}

create_source_database() {
  docker compose exec -T postgres createdb -U "$POSTGRES_USER" "$source_db"
}

seed_source_database() {
  docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$source_db" <<'SQL'
CREATE EXTENSION vector;
CREATE SCHEMA m3_proof;
CREATE TABLE m3_proof.recovery_records (
  id integer PRIMARY KEY,
  label text NOT NULL,
  embedding vector(3) NOT NULL
);
INSERT INTO m3_proof.recovery_records (id, label, embedding) VALUES
  (1, 'alpha', '[1,0,0]'),
  (2, 'beta',  '[0,1,0]'),
  (3, 'gamma', '[0,0,1]');
SQL
}

query_source_database() {
  docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$source_db" -Atc \
    "SELECT count(*) || '|' || string_agg(label, ',' ORDER BY id) || '|' || round(sum(embedding <-> '[0,0,0]'::vector)::numeric, 6) FROM m3_proof.recovery_records;"
}

create_backup() {
  docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" --no-owner --no-privileges --dbname "$source_db" | gzip -9 > "$backup_file"
}

create_restore_database() {
  docker compose exec -T postgres createdb -U "$POSTGRES_USER" "$restore_db"
}

restore_backup() {
  gunzip -c "$backup_file" | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$restore_db"
}

query_restored_database() {
  docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$restore_db" -Atc \
    "SELECT count(*) || '|' || string_agg(label, ',' ORDER BY id) || '|' || round(sum(embedding <-> '[0,0,0]'::vector)::numeric, 6) FROM m3_proof.recovery_records;"
}

run_probe create_source_database create_source_database
run_probe seed_source_database seed_source_database
run_probe source_data query_source_database
run_probe create_backup create_backup
run_probe backup_file test -s "$backup_file"
run_probe create_restore_database create_restore_database
run_probe restore_backup restore_backup
run_probe restored_data query_restored_database

{
  printf 'milestone=M3\n'
  printf 'captured_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'git_revision=%s\n' "$(git rev-parse HEAD)"
  printf 'source_database=%s\n' "$source_db"
  printf 'restore_database=%s\n' "$restore_db"
  printf 'backup_file=%s\n' "${backup_file#$root_dir/}"
  printf 'expected_result=%s\n' "$expected_row"
  printf 'capture_host=%s\n' "$(hostname)"
} > "$bundle_dir/manifest.txt"

sha256sum "$backup_file" > "$bundle_dir/backup.sha256"
(
  cd "$bundle_dir"
  sha256sum manifest.txt create_source_database.txt seed_source_database.txt source_data.txt create_backup.txt backup_file.txt create_restore_database.txt restore_backup.txt restored_data.txt backup.sha256 > SHA256SUMS
)

printf 'M3 recovery evidence bundle: %s\n' "$bundle_dir"
printf 'Synthetic databases retained: %s and %s\n' "$source_db" "$restore_db"
printf 'Compressed backup retained: %s\n' "$backup_file"
printf 'Verify it with: ./scripts/verify-m3-recovery-evidence.sh %q\n' "$bundle_dir"
exit "$status"
