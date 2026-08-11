#!/usr/bin/env bash
set -euo pipefail

# Run manually on the T480 from the repository root after M2 deployment.
# It captures raw, non-secret output from the real services into a local bundle.

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

if [[ ! -f .env ]]; then
  printf 'Refusing M2 evidence capture: .env is missing.\n' >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
bundle_dir="${M2_EVIDENCE_DIR:-$root_dir/evidence/M2}/$timestamp"
mkdir -p "$bundle_dir"

status=0
run_probe() {
  local id="$1"
  shift
  local output_file="$bundle_dir/${id}.txt"
  local started_at finished_at exit_code
  started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  {
    printf 'probe: %s\nstarted_at: %s\n' "$id" "$started_at"
    "$@"
  } >"$output_file" 2>&1 || exit_code=$?
  exit_code="${exit_code:-0}"
  finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'finished_at: %s\nexit_code: %s\n' "$finished_at" "$exit_code" >>"$output_file"
  if (( exit_code != 0 )); then
    status=1
  fi
}

run_probe configured_images docker compose config --images
run_probe image_ids docker compose images
run_probe compose_ps docker compose ps
run_probe health_check ./scripts/health-check.sh
run_probe n8n_health curl --fail --silent --show-error --max-time 10 http://127.0.0.1:5678/healthz
run_probe postgres_pgvector docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT current_database(), current_user, extname FROM pg_extension WHERE extname = 'vector';"
run_probe postgres_vector_distance docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT '[1,0,0]'::vector <-> '[0,1,0]'::vector AS l2_distance;"

{
  printf 'milestone=M2\n'
  printf 'captured_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'git_revision=%s\n' "$(git rev-parse HEAD)"
  printf 'capture_host=%s\n' "$(hostname)"
} >"$bundle_dir/manifest.txt"

(
  cd "$bundle_dir"
  sha256sum manifest.txt configured_images.txt image_ids.txt compose_ps.txt health_check.txt n8n_health.txt postgres_pgvector.txt postgres_vector_distance.txt > SHA256SUMS
)

printf 'M2 evidence bundle: %s\n' "$bundle_dir"
printf 'Verify it with: ./scripts/verify-m2-evidence.sh %q\n' "$bundle_dir"
exit "$status"
