#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"
status=0

note() { printf '%-8s %-18s %s\n' "$1" "$2" "$3"; }
ok() { note OK "$1" "$2"; }
warn() { note WARN "$1" "$2"; }
fail() { note FAIL "$1" "$2"; status=1; }

check_command() {
  local component="$1"
  local description="$2"
  shift 2
  if "$@" >/dev/null 2>&1; then
    ok "$component" "$description"
  else
    fail "$component" "$description"
  fi
}

service_id() {
  docker compose ps -q "$1" 2>/dev/null | head -n 1
}

check_service() {
  local service="$1"
  local container_id state health
  container_id="$(service_id "$service")"
  if [[ -z "$container_id" ]]; then
    fail "$service" "container is absent"
    return
  fi
  state="$(docker inspect --format '{{.State.Status}}' "$container_id" 2>/dev/null || true)"
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id" 2>/dev/null || true)"
  if [[ "$state" == "running" && "$health" == "healthy" ]]; then
    ok "$service" "running and healthy"
  else
    fail "$service" "state=$state health=$health"
  fi
}

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
else
  fail configuration '.env is missing'
fi

printf '%s\n' 'CS AI Lab health check'
printf '%-8s %-18s %s\n' STATUS COMPONENT DETAIL

check_command docker 'daemon is reachable' docker info
check_command compose 'configuration is valid' docker compose config --quiet

if ! docker info >/dev/null 2>&1; then
  warn checks 'Docker-dependent checks skipped because the daemon is unavailable'
  printf 'RESULT   %-18s %s\n' FAIL 'one or more required checks failed'
  exit 1
fi

for service in postgres n8n; do
  check_service "$service"
done

check_command postgres 'accepts database connections' \
  docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postgres}"
check_command postgres 'executes a database query' \
  docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postgres}" -Atqc 'SELECT 1'
check_command postgres 'pgvector extension is installed' \
  docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postgres}" -Atqc "SELECT 1 FROM pg_extension WHERE extname = 'vector'"

if command -v curl >/dev/null 2>&1; then
  check_command n8n 'host health endpoint responds' \
    curl --fail --silent --max-time 5 "http://${N8N_BIND_ADDRESS:-127.0.0.1}:5678/healthz"
else
  check_command n8n 'container health endpoint responds' \
    docker compose exec -T n8n wget -q --spider http://localhost:5678/healthz
fi

ollama_id="$(docker compose --profile ollama ps -q ollama 2>/dev/null | head -n 1)"
if [[ -n "$ollama_id" ]]; then
  check_service ollama
  check_command ollama 'model service responds' docker compose --profile ollama exec -T ollama ollama list
else
  note SKIP ollama 'optional profile is not running'
fi

disk_available_kb="$(df -Pk . | awk 'NR==2 {print $4}')"
disk_summary="$(df -h . | awk 'NR==2 {print $4 " available of " $2}')"
if [[ "$disk_available_kb" -lt 5242880 ]]; then
  warn capacity "disk low: $disk_summary"
else
  ok capacity "disk: $disk_summary"
fi

memory_available_kb="$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)"
memory_summary="$(free -h | awk '/^Mem:/ {print $7 " available of " $2}')"
if [[ "$memory_available_kb" -lt 524288 ]]; then
  warn capacity "memory low: $memory_summary"
else
  ok capacity "memory: $memory_summary"
fi

if [[ "$status" -eq 0 ]]; then
  printf 'RESULT   %-18s %s\n' PASS 'all required checks passed'
else
  printf 'RESULT   %-18s %s\n' FAIL 'one or more required checks failed'
fi
exit "$status"
