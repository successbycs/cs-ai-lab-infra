#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

if [[ ! -f .env ]]; then
  printf 'Refusing backup: .env is missing. Copy .env.example first.\n' >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
source .env
set +a

backup_dir="$root_dir/postgres/backup"
mkdir -p "$backup_dir"
timestamp="$(date +%Y%m%dT%H%M%S%z)"
backup_file="$backup_dir/${POSTGRES_DB}-${timestamp}.sql.gz"
temporary_file="${backup_file}.partial"

trap 'rm -f "$temporary_file"' EXIT
printf 'Creating PostgreSQL backup: %s\n' "$backup_file"
docker compose exec -T postgres pg_dump --clean --if-exists --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" </dev/null | gzip > "$temporary_file"
mv "$temporary_file" "$backup_file"
trap - EXIT
printf 'Backup complete: %s\n' "$backup_file"
