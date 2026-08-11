#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"
status=0
note() { printf '%-12s %s\n' "$1" "$2"; }
check() { if "$@" >/dev/null 2>&1; then note OK "$*"; else note FAIL "$*"; status=1; fi; }

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
else
  note FAIL '.env is missing'
  status=1
fi

note INFO 'CS AI Lab health check'
check docker info
check docker compose ps

for service in postgres n8n; do
  if docker compose ps --status running --services 2>/dev/null | grep -Fxq "$service"; then
    note OK "$service container is running"
  else
    note FAIL "$service container is not running"
    status=1
  fi
done

check docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postgres}"

if command -v curl >/dev/null 2>&1; then
  check curl --fail --silent --max-time 5 "http://${N8N_BIND_ADDRESS:-127.0.0.1}:5678/healthz"
else
  note INFO 'curl unavailable; skipped n8n HTTP check'
fi

note INFO "Disk: $(df -h . | awk 'NR==2 {print $4 " available of " $2}')"
note INFO "Memory: $(free -h | awk '/^Mem:/ {print $7 " available of " $2}')"
exit "$status"
