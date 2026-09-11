#!/usr/bin/env bash
set -euo pipefail
infra_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
target_config="${T480_TARGET_CONFIG:-$infra_root/.env.t480.local}"
token_file="${PENPOT_MCP_TOKEN_FILE:-/home/chris/.config/cs-ai-lab/penpot-mcp.token}"
state_dir="/home/chris/.config/cs-ai-lab"; port="${PENPOT_TUNNEL_PORT:-9001}"
[[ -f "$target_config" ]] || { printf 'Missing protected T480 target configuration.\n' >&2; exit 4; }
target="$(awk -F= '$1 == "T480_SSH_TARGET" { print $2; exit }' "$target_config")"
[[ "$target" =~ ^[A-Za-z0-9][A-Za-z0-9_.@:-]*$ ]] || { printf 'Invalid protected T480 target.\n' >&2; exit 4; }
[[ -f "$token_file" && "$(stat -c '%a' "$token_file")" == "600" ]] || { printf 'Missing mode-0600 Penpot MCP token file: %s\n' "$token_file" >&2; exit 4; }
token="$(tr -d '\r\n' < "$token_file")"; [[ ${#token} -ge 20 ]] || { printf 'Penpot MCP token is absent or invalid.\n' >&2; exit 4; }
install -d -m 0700 "$state_dir"; pid_file="$state_dir/penpot-ssh-proxy.pid"; log_file="$state_dir/penpot-ssh-proxy.log"
# Reuse an already-running loopback proxy, which also keeps the browser-facing
# origin aligned with Penpot's configured public URI (localhost:9001).
if ! curl --fail --silent --max-time 2 "http://127.0.0.1:${port}/" >/dev/null; then
  if [[ -f "$pid_file" ]] && kill -0 "$(<"$pid_file")" 2>/dev/null; then kill "$(<"$pid_file")"; fi
  nohup python3 "$infra_root/penpot/scripts/penpot_ssh_proxy.py" --target "$target" --port "$port" >"$log_file" 2>&1 &
  printf '%s\n' "$!" > "$pid_file"
fi
for _ in $(seq 1 20); do curl --fail --silent --max-time 2 "http://127.0.0.1:${port}/" >/dev/null && break; sleep 1; done
curl --fail --silent --max-time 5 "http://127.0.0.1:${port}/" >/dev/null
codex mcp remove penpot_t480 >/dev/null 2>&1 || true
codex mcp add penpot_t480 --url "http://127.0.0.1:${port}/mcp/stream?userToken=$token" >/dev/null
chmod 0600 /home/chris/.codex/config.toml; unset token
printf 'PENPOT_GLOBAL_CODEX_MCP_OK endpoint=http://127.0.0.1:%s scope=user_all_repositories=true\n' "$port"
