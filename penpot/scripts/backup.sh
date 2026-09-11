#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$script_dir/lib.sh"

require_env_file
# shellcheck disable=SC1090
source "$PENPOT_ENV_FILE"
umask 077
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_root="$PENPOT_ROOT/backups/$timestamp"
temporary_root="$PENPOT_ROOT/backups/.${timestamp}.partial"
install -d -m 0700 "$temporary_root"
trap 'rm -rf -- "$temporary_root"' EXIT

compose exec -T penpot-postgres pg_dump \
  --username penpot --dbname penpot --format=custom --clean --if-exists \
  > "$temporary_root/penpot.dump"
compose exec -T penpot-frontend tar -C /opt/data/assets -czf - . \
  > "$temporary_root/assets.tar.gz"

compose config --images > "$temporary_root/images.txt"
git -C "$(dirname "$PENPOT_ROOT")" rev-parse HEAD > "$temporary_root/source-revision.txt"
{
  printf 'captured_at_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'scope=penpot_database_and_assets\n'
  printf 'secrets_included=false\n'
  printf 'valkey_included=false_transient_coordination_only\n'
  printf 'restore_requires_external_penpot_env=true\n'
} > "$temporary_root/metadata.txt"
(cd "$temporary_root" && sha256sum assets.tar.gz images.txt metadata.txt penpot.dump source-revision.txt > SHA256SUMS)
mv "$temporary_root" "$backup_root"
trap - EXIT

retention_days="${PENPOT_BACKUP_RETENTION_DAYS:-14}"
[[ "$retention_days" =~ ^[0-9]+$ ]] || {
  printf 'Invalid PENPOT_BACKUP_RETENTION_DAYS.\n' >&2
  exit 4
}
find "$PENPOT_ROOT/backups" -mindepth 1 -maxdepth 1 -type d \
  -name '20??????T??????Z' -mtime "+$retention_days" -print -exec rm -rf -- {} +

printf 'PENPOT_BACKUP_OK bundle=%s retention_days=%s\n' "$backup_root" "$retention_days"
sha256sum "$backup_root/SHA256SUMS"
