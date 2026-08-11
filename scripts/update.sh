#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

printf 'Current image IDs:\n'
docker compose images || true
printf '\nPulling the deliberately pinned images (this does not restart services):\n'
docker compose pull
printf '\nImage IDs after pull:\n'
docker compose images
printf '\nTo upgrade, first edit compose.yaml to a reviewed tag and matching digest, then rerun this script.\n'
printf 'Review release notes and backups, then restart deliberately with: docker compose up -d\n'
