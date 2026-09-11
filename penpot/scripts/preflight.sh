#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$script_dir/lib.sh"

command -v docker >/dev/null
docker info >/dev/null
docker compose version >/dev/null

available_kib="$(df -Pk / | awk 'NR==2 {print $4}')"
(( available_kib >= 12582912 )) || {
  printf 'PENPOT_PREFLIGHT_BLOCKED reason=less_than_12GiB_free\n' >&2
  exit 4
}

if ss -ltnH '( sport = :9001 )' | grep -q .; then
  if ! docker ps --format '{{.Names}}' | grep -qx 'penpot-private-penpot-frontend-1'; then
    printf 'PENPOT_PREFLIGHT_BLOCKED reason=port_9001_in_use\n' >&2
    exit 4
  fi
fi

printf 'PENPOT_PREFLIGHT_OK docker=true compose=true free_gib=%s port_9001=available_or_penpot\n' "$((available_kib / 1024 / 1024))"
