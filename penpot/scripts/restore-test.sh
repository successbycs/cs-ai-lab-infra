#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$script_dir/lib.sh"

require_env_file
backup_root="$(find "$PENPOT_ROOT/backups" -mindepth 1 -maxdepth 1 -type d -name '20??????T??????Z' -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)"
[[ -n "$backup_root" && -f "$backup_root/SHA256SUMS" ]] || {
  printf 'No Penpot backup bundle is available.\n' >&2
  exit 4
}
(cd "$backup_root" && sha256sum -c SHA256SUMS >/dev/null)

suffix="$(date -u +%Y%m%d%H%M%S)"
container_name="penpot-restore-test-$suffix"
database_volume="penpot_restore_test_${suffix}_db"
assets_volume="penpot_restore_test_${suffix}_assets"
temporary_password="$(openssl rand -hex 24)"
postgres_image='postgres:15.18-bookworm@sha256:e8db9bd3e9e1751eb639fb17be53cc6d1b62a322adf75b99e791767a7a16ce69'
frontend_image='penpotapp/frontend:2.17.2@sha256:94fa2864d8fc0cd62245af95c03cca89306a7fd23c206a98a3e9dc9a376ea27e'

cleanup() {
  docker rm -f "$container_name" >/dev/null 2>&1 || true
  docker volume rm "$database_volume" "$assets_volume" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker volume create "$database_volume" >/dev/null
docker volume create "$assets_volume" >/dev/null
docker run -d --name "$container_name" \
  -e POSTGRES_DB=penpot_restore_test \
  -e POSTGRES_USER=penpot_restore_test \
  -e POSTGRES_PASSWORD="$temporary_password" \
  -v "$database_volume:/var/lib/postgresql/data" \
  "$postgres_image" >/dev/null

for attempt in $(seq 1 60); do
  if docker exec "$container_name" pg_isready -U penpot_restore_test -d penpot_restore_test >/dev/null 2>&1; then
    break
  fi
  [[ "$attempt" != "60" ]] || { printf 'Isolated restore database did not become ready.\n' >&2; exit 5; }
  sleep 2
done

docker exec -i "$container_name" pg_restore \
  --username penpot_restore_test --dbname penpot_restore_test \
  --no-owner --no-privileges < "$backup_root/penpot.dump"
docker run --rm -i -v "$assets_volume:/restore" "$frontend_image" \
  tar -C /restore -xzf - < "$backup_root/assets.tar.gz"

profile_count="$(docker exec "$container_name" psql -U penpot_restore_test -d penpot_restore_test -Atqc 'select count(*) from profile')"
file_count="$(docker exec "$container_name" psql -U penpot_restore_test -d penpot_restore_test -Atqc 'select count(*) from file')"
asset_entries="$(docker run --rm -v "$assets_volume:/restore:ro" "$frontend_image" find /restore -mindepth 1 -print | wc -l)"
[[ "$profile_count" =~ ^[0-9]+$ && "$file_count" =~ ^[0-9]+$ && "$asset_entries" =~ ^[0-9]+$ ]]

printf 'PENPOT_RESTORE_TEST_OK isolated=true profiles=%s files=%s asset_entries=%s cleanup=automatic\n' \
  "$profile_count" "$file_count" "$asset_entries"
