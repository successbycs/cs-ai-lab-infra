#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$script_dir/lib.sh"

require_env_file
compose config --quiet
compose pull
compose up -d --wait --wait-timeout 300
"$script_dir/health.sh"
