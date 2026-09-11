#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$script_dir/lib.sh"

require_env_file
before_profiles="$(compose exec -T penpot-postgres psql -U penpot -d penpot -Atqc 'select count(*) from profile')"
before_files="$(compose exec -T penpot-postgres psql -U penpot -d penpot -Atqc 'select count(*) from file')"
before_database_volume="$(compose config --volumes | grep -x penpot_postgres)"
before_assets_volume="$(compose config --volumes | grep -x penpot_assets)"

compose restart
for attempt in $(seq 1 60); do
  if curl --fail --silent --max-time 5 http://127.0.0.1:9001/api/health >/dev/null 2>&1; then
    break
  fi
  [[ "$attempt" != "60" ]] || { printf 'Penpot did not recover after controlled restart.\n' >&2; exit 5; }
  sleep 2
done

after_profiles="$(compose exec -T penpot-postgres psql -U penpot -d penpot -Atqc 'select count(*) from profile')"
after_files="$(compose exec -T penpot-postgres psql -U penpot -d penpot -Atqc 'select count(*) from file')"
[[ "$before_profiles" == "$after_profiles" && "$before_files" == "$after_files" ]]
[[ "$before_database_volume" == penpot_postgres && "$before_assets_volume" == penpot_assets ]]
printf 'PENPOT_PERSISTENCE_OK profiles=%s files=%s volumes=database,assets,valkey\n' "$after_profiles" "$after_files"
