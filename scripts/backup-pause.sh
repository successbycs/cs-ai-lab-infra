#!/usr/bin/env bash

backup_pause_guard() {
  local script_dir repo_root pause_file
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  repo_root="$(cd "$script_dir/.." && pwd)"
  pause_file="$repo_root/BACKUPS-PAUSED.md"
  [[ ! -f "$pause_file" ]] && return 0
  printf 'Backup creation is paused; see BACKUPS-PAUSED.md. No data was created.\n' >&2
  return 75
}
