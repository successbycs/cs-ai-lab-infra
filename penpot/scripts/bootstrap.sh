#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$script_dir/lib.sh"

install -d -m 0700 "$(dirname "$PENPOT_ENV_FILE")"
if [[ ! -f "$PENPOT_ENV_FILE" ]]; then
  umask 077
  database_password="$(openssl rand -hex 32)"
  secret_key="$(openssl rand -base64 64 | tr -d '\n')"
  {
    printf 'PENPOT_DATABASE_PASSWORD=%s\n' "$database_password"
    printf 'PENPOT_SECRET_KEY=%s\n' "$secret_key"
    printf 'PENPOT_PUBLIC_URI=http://localhost:9001\n'
    printf 'PENPOT_BIND_ADDRESS=127.0.0.1\n'
    printf 'PENPOT_HTTP_PORT=9001\n'
    printf 'PENPOT_FLAGS="enable-login-with-password enable-prepl-server enable-mcp enable-access-tokens disable-registration disable-email-verification disable-secure-session-cookies"\n'
    printf 'PENPOT_BACKUP_RETENTION_DAYS=14\n'
    printf 'TZ=Pacific/Auckland\n'
  } > "$PENPOT_ENV_FILE"
  chmod 0600 "$PENPOT_ENV_FILE"
fi

require_env_file
if grep -Eq 'CHANGE_ME|change-this|^PENPOT_DATABASE_PASSWORD=penpot$' "$PENPOT_ENV_FILE"; then
  printf 'Refusing insecure Penpot secrets.\n' >&2
  exit 4
fi

compose config --quiet
resolved_port="$(compose config | sed -n '/published:/s/.*published: *"\{0,1\}\([^" ]*\).*/\1/p' | head -n 1)"
resolved_host="$(compose config | sed -n '/host_ip:/s/.*host_ip: *"\{0,1\}\([^" ]*\).*/\1/p' | head -n 1)"
[[ "$resolved_port" == "9001" && "$resolved_host" == "127.0.0.1" ]] || {
  printf 'Refusing non-loopback or unexpected Penpot publication.\n' >&2
  exit 4
}
printf 'PENPOT_BOOTSTRAP_OK env_mode=0600 bind=127.0.0.1 port=9001\n'
