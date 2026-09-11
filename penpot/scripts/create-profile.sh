#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$script_dir/lib.sh"

require_env_file
read -r -p 'Full name: ' profile_name
read -r -p 'Email: ' profile_email
read -r -s -p 'Password (10+ characters): ' profile_password
printf '\n'
read -r -s -p 'Repeat password: ' profile_password_repeat
printf '\n'

[[ ${#profile_name} -ge 2 && "$profile_email" == *@* && ${#profile_password} -ge 10 ]] || {
  printf 'Name, email, or password does not meet the local policy.\n' >&2
  exit 4
}
[[ "$profile_password" == "$profile_password_repeat" ]] || {
  printf 'Passwords do not match.\n' >&2
  exit 4
}

compose exec -T penpot-backend python3 manage.py create-profile \
  -n "$profile_name" -e "$profile_email" -p "$profile_password" \
  --skip-tutorial --skip-walkthrough
unset profile_password profile_password_repeat
printf 'PENPOT_PROFILE_CREATED email=%s\n' "$profile_email"
