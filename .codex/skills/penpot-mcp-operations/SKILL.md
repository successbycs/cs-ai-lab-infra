---
name: penpot-mcp-operations
description: Operate, troubleshoot, or review the isolated Penpot deployment and loopback-only MCP access path.
---

# Penpot MCP operations

Use for the Penpot stack, its MCP endpoint, relay, dedicated service browser,
or backup and recovery procedures. Read [Penpot README](../../../penpot/README.md)
and [MCP access](../../../penpot/MCP.md); for transport work also read
[the durable MCP plan](../../../penpot/EXECPLAN-durable-mcp.md).

- Preserve Penpot's separate digest-pinned, loopback-only Compose deployment.
  Use its provided lifecycle scripts and governed T480 operations rather than
  broad Docker commands.
- The MCP path may expose only the documented four remote tools. Never mount a
  checkout, Docker socket, host shell, `.env`, SSH key, or unrelated credential
  into Penpot MCP components.
- Keep the relay at loopback and retain its client bound. Never expose port
  9001 or create a firewall/router exception for MCP.
- The connected Penpot file must be open in the dedicated service identity's
  interactive Windows browser. Services and scheduled tasks cannot replace
  that attachment; do not use the owner browser profile.
- Keep MCP tokens only in protected local client configuration. Smoke tests,
  diagnostics, and documentation must not reveal them.

For a change, run the smallest relevant preflight, health, smoke, backup, or
restore test and report the verified boundary as well as service status.
