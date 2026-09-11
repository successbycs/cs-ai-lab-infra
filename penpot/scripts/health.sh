#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$script_dir/lib.sh"

require_env_file
compose config --quiet
compose ps --status running --services | sort > /tmp/penpot-running-services.txt
expected_services=$'penpot-backend\npenpot-exporter\npenpot-frontend\npenpot-mcp\npenpot-postgres\npenpot-valkey'
[[ "$(cat /tmp/penpot-running-services.txt)" == "$expected_services" ]] || {
  printf 'PENPOT_HEALTH_FAIL reason=required_service_not_running\n' >&2
  compose ps >&2
  exit 5
}

curl --fail --silent --show-error --max-time 10 http://127.0.0.1:9001/ >/dev/null
compose exec -T penpot-postgres psql -U penpot -d penpot -Atqc 'select 1' | grep -qx 1
compose exec -T penpot-valkey valkey-cli ping | grep -qx PONG

published="$(compose port penpot-frontend 8080)"
[[ "$published" == '127.0.0.1:9001' ]] || {
  printf 'PENPOT_HEALTH_FAIL reason=unexpected_publication publication=%s\n' "$published" >&2
  exit 5
}

mcp_id="$(compose ps -q penpot-mcp)"
[[ -n "$mcp_id" ]]
[[ "$(docker inspect -f '{{.HostConfig.Privileged}}' "$mcp_id")" == 'false' ]]
[[ "$(docker inspect -f '{{len .Mounts}}' "$mcp_id")" == '0' ]]
[[ "$(docker inspect -f '{{.HostConfig.ReadonlyRootfs}}' "$mcp_id")" == 'true' ]]
docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$mcp_id" | grep -qx 'PENPOT_MCP_REMOTE_MODE=true'

printf 'PENPOT_HEALTH_OK services=6 endpoint=http://127.0.0.1:9001 mcp_mounts=0 mcp_remote_mode=true\n'
