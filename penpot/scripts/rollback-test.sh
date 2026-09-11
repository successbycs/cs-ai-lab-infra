#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$script_dir/lib.sh"

require_env_file
before_ids="$(compose ps -q | sort)"
before_images="$(compose config --images | sort)"
temporary_override="$(mktemp)"
trap 'rm -f -- "$temporary_override"' EXIT
printf '%s\n' \
  'services:' \
  '  penpot-frontend:' \
  '    image: invalid.invalid/penpot-upgrade-does-not-exist:rollback-test' \
  > "$temporary_override"

set +e
docker compose --project-directory "$PENPOT_ROOT" --env-file "$PENPOT_ENV_FILE" \
  -f "$PENPOT_ROOT/compose.yaml" -f "$temporary_override" pull penpot-frontend \
  >/dev/null 2>&1
failed_pull_status=$?
set -e
[[ "$failed_pull_status" -ne 0 ]] || {
  printf 'Rollback test did not produce the expected isolated pull failure.\n' >&2
  exit 5
}

after_failed_pull_ids="$(compose ps -q | sort)"
[[ "$before_ids" == "$after_failed_pull_ids" ]]
compose up -d --wait --wait-timeout 300
after_images="$(compose config --images | sort)"
[[ "$before_images" == "$after_images" ]]
"$script_dir/health.sh" >/dev/null
printf 'PENPOT_ROLLBACK_TEST_OK failed_candidate_not_started=true prior_config_reapplied=true\n'
