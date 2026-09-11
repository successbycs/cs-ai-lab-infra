#!/usr/bin/env bash
# Start the interactive, password-safe Penpot profile creator on the T480.
set -euo pipefail

infra_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
target_config="${T480_TARGET_CONFIG:-$infra_root/.env.t480.local}"
[[ -f "$target_config" ]] || { printf 'Missing protected T480 target configuration.\n' >&2; exit 4; }

target="$(awk -F= '$1 == "T480_SSH_TARGET" { print $2; exit }' "$target_config")"
[[ "$target" =~ ^[A-Za-z0-9][A-Za-z0-9_.@:-]*$ ]] || { printf 'Invalid protected T480 target.\n' >&2; exit 4; }

# The target is validated above and the remote command is deliberately fixed;
# credentials are entered only into the T480's interactive profile script.
remote_command="wsl.exe -d Ubuntu -- bash /home/chris/projects/cs-ai-lab-infra/penpot/scripts/create-profile.sh"
exec powershell.exe -NoProfile -NonInteractive -Command \
  "& ssh.exe -tt -o BatchMode=yes -o StrictHostKeyChecking=yes ${target} '${remote_command}'"
