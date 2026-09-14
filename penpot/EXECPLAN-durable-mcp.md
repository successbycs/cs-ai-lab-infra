# Durable Penpot MCP execution plan

## Objective

Replace a manually maintained owner-browser tab and unbounded SSH request
relay with a durable, least-privilege path:

1. one persistent SSH transport on the controller;
2. a dedicated interactive T480 Windows service-account browser that opens
   the file and attaches MCP; and
3. a loopback-only controller endpoint consumed by Codex.

The browser and tunnel are deliberately separate. The tunnel has no Penpot
credentials; the browser holds the Penpot service identity; the controller
holds the protected MCP token.

## Current safe state

The current bootstrap uses `127.0.0.1:19001`, not Penpot's own port 9001. It
has a bounded fallback transport (four active streams) and reaps a Windows SSH
child when either half of an HTTP/SSE stream ends. This is deployed locally and
verified with repeated HTTP requests. It is safe to keep using while the
persistent Windows tunnel is installed.

Windows OpenSSH 9.5 on this controller cannot use Unix `ControlMaster` socket
multiplexing (`getsockname failed: Not a socket`). Do not retry that design.

## Cutover prerequisites

- An administrator-approved Windows firewall rule limited to the WSL virtual
  subnet, never the LAN or Internet.
- A dedicated Windows sign-in/profile for the Penpot service identity. This is
  not Chris's owner browser profile.
- A protected SSH authentication method usable by the persistent tunnel task.
  Do not copy private keys or passwords into this repository, Task Scheduler
  XML, arguments, or logs.
- The service identity is a Penpot member of only the intended design team and
  file.

## Install the persistent transport

1. On the controller, determine the WSL gateway address (`ip route`); bind the
   Windows SSH SOCKS listener only to that address and an unused high port.
2. As Windows administrator, allow inbound TCP to that exact port from only
   the WSL virtual subnet. Confirm there is no broad `Any` remote-address rule.
3. Start one Windows SSH process with strict host-key checking, batch mode,
   server-alive checks, and dynamic forwarding. It must be supervised by the
   approved service mechanism and restarted after failure.
4. From WSL, verify a SOCKS5 request reaches the T480's `127.0.0.1:9001`.
5. Replace the fallback relay's per-request SSH transport with a SOCKS5 stream
   adapter, retain the four-client cap, and verify no child SSH process is
   created per MCP request.
6. Stop the fallback proxy only after the SOCKS adapter has passed the health
   and disconnect tests.

Do not bind the SOCKS listener to `0.0.0.0`, do not create a router port
forward, and do not expose Penpot's port 9001.

## Service-account browser procedure

1. Sign in to the dedicated Windows service account on the T480.
2. Run `scripts/managed-service-browser.ps1` with the known existing dedicated
   Chrome user-data directory and the exact Penpot file URL.
3. Confirm the account in Penpot is the service identity, not Chris's owner.
4. In the file, choose **File → MCP Server → Connect** and keep that tab open.
5. From the controller, run a harmless MCP read. A connection error means the
   tab is not attached; it does not mean the data or design is missing.

The launcher never creates a browser profile, authenticates a user, reads
cookies, or prints credentials. A Windows service or scheduled task cannot
substitute for this browser attachment because it runs outside the interactive
desktop session.

## Acceptance checks

- Controller relay is only reachable at loopback.
- Persistent SSH transport is one process and survives an MCP client restart.
- WSL cannot reach the Windows tunnel from any address outside the permitted
  virtual subnet.
- The relay maintains at most four active data streams and leaves no orphan
  `ssh -W` children after a client disconnect.
- A dedicated service browser, with the intended file open, completes an MCP
  read; closing the file makes operations fail safely.
- No token, browser cookie, service password, private key, or remote target is
  committed or emitted in logs.

## Rollback

Stop the persistent tunnel task/process, remove its narrow firewall rule, and
run `bootstrap-global-codex-mcp.sh` to restore the verified bounded fallback.
Disconnect the file's MCP attachment if access must end immediately. For a
token incident, rotate/revoke the token according to `MCP.md`; never merely
restart the relay.
