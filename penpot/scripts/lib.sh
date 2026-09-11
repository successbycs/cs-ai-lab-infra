#!/usr/bin/env bash
set -euo pipefail

PENPOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PENPOT_ENV_FILE="${PENPOT_ENV_FILE:-/home/chris/.config/cs-ai-lab/penpot.env}"
PENPOT_VERIFICATION_FILE="${PENPOT_VERIFICATION_FILE:-/home/chris/.config/cs-ai-lab/penpot-verification.env}"

require_env_file() {
  [[ -f "$PENPOT_ENV_FILE" ]] || {
    printf 'Penpot environment file is missing: %s\n' "$PENPOT_ENV_FILE" >&2
    exit 4
  }
  [[ "$(stat -c '%a' "$PENPOT_ENV_FILE")" == "600" ]] || {
    printf 'Penpot environment file must have mode 0600.\n' >&2
    exit 4
  }
}

compose() {
  docker compose \
    --project-directory "$PENPOT_ROOT" \
    --env-file "$PENPOT_ENV_FILE" \
    -f "$PENPOT_ROOT/compose.yaml" "$@"
}
