#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$script_dir/lib.sh"

require_env_file
install -d -m 0700 "$(dirname "$PENPOT_VERIFICATION_FILE")"
if [[ ! -f "$PENPOT_VERIFICATION_FILE" ]]; then
  umask 077
  {
    printf 'PENPOT_TEST_EMAIL=mcp-verification@penpot.invalid\n'
    printf 'PENPOT_TEST_PASSWORD=%s\n' "$(openssl rand -hex 32)"
  } > "$PENPOT_VERIFICATION_FILE"
  chmod 0600 "$PENPOT_VERIFICATION_FILE"
fi
# shellcheck disable=SC1090
source "$PENPOT_VERIFICATION_FILE"

profile_count="$(compose exec -T penpot-postgres psql -U penpot -d penpot -Atqc "select count(*) from profile where email = 'mcp-verification@penpot.invalid'")"
if [[ "$profile_count" == "0" ]]; then
  compose exec -T penpot-backend python3 manage.py create-profile \
    -n 'MCP Verification Agent' \
    -e "$PENPOT_TEST_EMAIL" \
    -p "$PENPOT_TEST_PASSWORD" \
    --skip-tutorial --skip-walkthrough >/dev/null
fi
unset PENPOT_TEST_PASSWORD
printf 'PENPOT_VERIFICATION_PROFILE_OK email=mcp-verification@penpot.invalid credential_file_mode=0600\n'
