#!/usr/bin/env bash
set -euo pipefail

# Capture a complete, local-only recovery bundle on the T480. This command is
# deliberately approval-gated because it reads .env, creates archives, and
# reads named volumes. It never copies a key, .env, or destination credential.

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

approve=false
n8n_quiesced=false
while (($#)); do
  case "$1" in
    --approve) approve=true ;;
    --n8n-quiesced) n8n_quiesced=true ;;
    *) printf 'Usage: %s --approve --n8n-quiesced\n' "$0" >&2; exit 2 ;;
  esac
  shift
done
[[ "$approve" == true ]] || { printf 'Refusing recovery capture without --approve after explicit operator approval.\n' >&2; exit 2; }
[[ "$n8n_quiesced" == true ]] || { printf 'Refusing recovery capture until the operator confirms n8n writes are quiesced.\n' >&2; exit 2; }
[[ -f .env ]] || { printf 'Refusing recovery capture: .env is missing.\n' >&2; exit 2; }
[[ -f .w1-recovery.local ]] || { printf 'Refusing recovery capture: .w1-recovery.local with opaque recovery record IDs is missing.\n' >&2; exit 2; }

set -a
# shellcheck disable=SC1091
source .env
# shellcheck disable=SC1091
source .w1-recovery.local
set +a
[[ -n "${W1_ENVIRONMENT_RECOVERY_RECORD_ID:-}" && -n "${W1_N8N_ENCRYPTION_KEY_RECOVERY_RECORD_ID:-}" ]] || {
  printf 'Refusing recovery capture: both opaque recovery record IDs are required.\n' >&2; exit 2;
}
[[ "${W1_RECOVERY_RECORDS_CONFIRMED:-no}" == yes ]] || {
  printf 'Refusing recovery capture: owner-controlled environment and n8n-key records are not confirmed.\n' >&2; exit 2;
}
[[ "${W1_OLLAMA_MODEL_DISPOSITION:-}" == redownload-reviewed-models ]] || {
  printf 'Refusing recovery capture: the approved Ollama disposition is redownload-reviewed-models.\n' >&2; exit 2;
}
[[ "${W1_RPO_HOURS:-0}" =~ ^[1-9][0-9]*$ && "${W1_RTO_HOURS:-0}" =~ ^[1-9][0-9]*$ && "${W1_T16_RETENTION_DAILY:-0}" =~ ^[1-9][0-9]*$ ]] || {
  printf 'Refusing recovery capture: RPO, RTO, and T16 retention must be positive integers.\n' >&2; exit 2;
}

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
bundle_dir="$root_dir/postgres/backup/full-lab/w1-$timestamp"
temporary_dir="${bundle_dir}.partial"
n8n_image="n8nio/n8n:1.123.76@sha256:66b6bfd6716877591d9c21340250f44f842e6b03f97ccaed09b9f95e13cf5331"

volume_for() {
  local role="$1" volume
  volume="$(docker volume ls -q --filter label=com.docker.compose.project=cs-ai-lab --filter label=com.docker.compose.volume="$role")"
  [[ "$(printf '%s\n' "$volume" | sed '/^$/d' | wc -l)" -eq 1 ]] || {
    printf 'Expected exactly one cs-ai-lab %s volume; refusing capture.\n' "$role" >&2; return 1;
  }
  printf '%s\n' "$volume"
}

mkdir -p "$(dirname "$bundle_dir")"
[[ ! -e "$bundle_dir" && ! -e "$temporary_dir" ]] || { printf 'Recovery bundle destination already exists.\n' >&2; exit 2; }
mkdir "$temporary_dir"
trap 'rm -rf "$temporary_dir"' EXIT

n8n_data_volume="$(volume_for n8n_data)"
n8n_files_volume="$(volume_for n8n_files)"
docker compose exec -T postgres pg_dump --clean --if-exists --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" </dev/null | gzip -9 > "$temporary_dir/postgres.sql.gz"
docker run --rm --entrypoint /bin/sh -v "$n8n_data_volume:/source:ro" -v "$temporary_dir:/backup" "$n8n_image" -c 'tar -C /source -czf /backup/n8n-data.tar.gz .'
docker run --rm --entrypoint /bin/sh -v "$n8n_files_volume:/source:ro" -v "$temporary_dir:/backup" "$n8n_image" -c 'tar -C /source -czf /backup/n8n-files.tar.gz .'
python3 scripts/backup_manifest.py create-full-lab \
  --dump "$temporary_dir/postgres.sql.gz" \
  --n8n-data-archive "$temporary_dir/n8n-data.tar.gz" \
  --n8n-files-archive "$temporary_dir/n8n-files.tar.gz" \
  --compose compose.yaml \
  --source-revision "$(git rev-parse HEAD)" \
  --environment-recovery-record-id "$W1_ENVIRONMENT_RECOVERY_RECORD_ID" \
  --n8n-encryption-key-recovery-record-id "$W1_N8N_ENCRYPTION_KEY_RECOVERY_RECORD_ID" \
  --output "$temporary_dir/manifest.json"
python3 scripts/backup_manifest.py verify "$temporary_dir/manifest.json" --require-full-lab
mv "$temporary_dir" "$bundle_dir"
trap - EXIT
printf 'Full-lab recovery bundle captured: %s\n' "$bundle_dir"
printf 'No transfer occurred. Pull this named bundle from the prepared T16 only after separate approval.\n'
