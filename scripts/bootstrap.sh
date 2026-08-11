#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

failures=0
check_command() {
  if command -v "$1" >/dev/null 2>&1; then
    printf 'OK: %s\n' "$2"
  else
    printf 'MISSING: %s\n' "$2" >&2
    failures=$((failures + 1))
  fi
}

printf 'CS AI Lab bootstrap check (no system changes will be made)\n'
case "$(uname -s)" in
  Linux) printf 'OK: Linux host detected\n' ;;
  *) printf 'WARNING: This lab is designed for a Linux T480; detected %s\n' "$(uname -s)" ;;
esac
check_command docker 'Docker CLI'
check_command git 'Git'

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  printf 'OK: Docker Compose plugin\n'
else
  printf 'MISSING: Docker Compose plugin\n' >&2
  failures=$((failures + 1))
fi

if [[ ! -f .env ]]; then
  printf 'MISSING: .env (copy .env.example and replace placeholders)\n' >&2
  failures=$((failures + 1))
elif grep -q 'CHANGE_ME' .env; then
  printf 'WARNING: .env still contains one or more placeholder values\n' >&2
  failures=$((failures + 1))
else
  printf 'OK: .env exists without template placeholders\n'
fi

if (( failures > 0 )); then
  printf '\nResolve the items above, then run: docker compose config\n' >&2
  exit 1
fi

printf '\nPrerequisites look ready. Next: docker compose config && docker compose up -d\n'
