# Penpot MCP access for Codex and OpenWorker

## Security boundary

The only approved agent path is:

```text
Codex/OpenWorker MCP client
  -> authenticated SSH local forward (operator-owned)
  -> T480 127.0.0.1:9001/mcp/stream?userToken=...
  -> penpot-frontend proxy
  -> penpot-mcp (remote mode, no mounts)
  -> bundled Penpot plugin
  -> the file explicitly open and connected in the service account browser
```

The MCP server does not receive a repository checkout, Docker socket, host
shell, `.env` file, SSH key, Vercel/Supabase credential, or production data.
Do not add any of those mounts or environment variables. The expected remote
tool set is exactly `execute_code`, `export_shape`, `get_high_level_overview`,
and `get_penpot_api_info`; `mcp-smoke.mjs` fails closed if it differs.

The service account is a Penpot design identity, not a host account. Put only
the intended design project/files in its team. Keep Chris's owner account
separate. For each agent session, open the intended file in the service
account browser, choose **File → MCP Server → Connect**, and keep that tab
active. Disconnect or close the tab at the end.

## Local forward

From an approved controller with the existing strict host-key SSH profile:

```bash
ssh -N -o BatchMode=yes -o StrictHostKeyChecking=yes \
  -L 127.0.0.1:9001:127.0.0.1:9001 t480
```

This opens no T480 firewall or router port. If local port 9001 is occupied,
use a different left-hand port and keep the remote side at `127.0.0.1:9001`.

## Create and store an MCP key

Sign in as the dedicated Penpot agent account, open **Your account →
Integrations → MCP Server**, enable it, and create a short-lived key. Store it
only in the client's protected user configuration/secret store. The URL form
for this self-hosted Compose deployment is:

```text
http://127.0.0.1:9001/mcp/stream?userToken=REDACTED
```

Never put the completed URL in Git, application repositories, screenshots,
shell history, tickets, or chat.

## Codex

Codex supports project-scoped MCP configuration in a trusted project's
`.codex/config.toml`, but the token must not be committed. For this shared
service use the mode-0600 user file `~/.codex/config.toml`:

```toml
[mcp_servers.penpot_t480]
url = "http://127.0.0.1:9001/mcp/stream?userToken=REDACTED"
enabled = true
required = false
enabled_tools = ["execute_code", "export_shape", "get_high_level_overview", "get_penpot_api_info"]
default_tools_approval_mode = "writes"
tool_timeout_sec = 120
```

Restart the Codex client after editing and confirm with `codex mcp list` or
`/mcp`. OpenAI's current configuration reference is
<https://learn.chatgpt.com/docs/extend/mcp?surface=cli>.

## OpenWorker

Configure the same streamable-HTTP URL only in OpenWorker's protected runtime
secret/configuration, outside its project workspaces. Allow only the four tool
names above and require approval for `execute_code`. Do not mount
`/home/chris/projects`, the Docker socket, or the infrastructure secret
directory into an MCP sidecar. If the current OpenWorker release cannot source
the token without persisting it in a repository or cannot apply a tool
allowlist, leave Penpot MCP disabled for OpenWorker until that boundary exists.

## Rotation and revocation

Create a replacement MCP key in Penpot, update the protected client config,
restart the client, verify the new key, then delete the old key in Penpot.
Emergency revocation is immediate: disconnect the file, delete the key, stop
the SSH forward, and optionally run `penpot_disable` to stop the whole stack.
After revocation, a former client may still initialize a stateless connection,
but design operations must fail because no authenticated plugin route remains;
verify with a read call, not only `tools/list`.
