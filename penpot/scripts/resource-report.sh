#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$script_dir/lib.sh"

require_env_file
mapfile -t container_ids < <(compose ps -q)
(( ${#container_ids[@]} == 6 )) || {
  printf 'Expected six running Penpot containers.\n' >&2
  exit 5
}
docker stats --no-stream --format '{{.Name}} cpu={{.CPUPerc}} memory={{.MemUsage}}' "${container_ids[@]}" | sort
printf 'penpot_volume_usage=' 
docker system df -v | awk '/penpot-private_penpot_(assets|postgres|valkey)/ {sum += $4} END {print sum "B_reported_fields_require_unit_review"}'
df -h / | awk 'NR==2 {printf "wsl_root_used=%s wsl_root_available=%s wsl_root_use=%s\n", $3, $4, $5}'
