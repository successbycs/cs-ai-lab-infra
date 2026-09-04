# M10 execution prompt — private remote access over tailnet

M10 must not start until M5 is proven. It is an access and resilience outcome, not permission to expose the T480 publicly or to bundle unrelated remediation.

## Agreed scope

- Tailnet owner: `chris@successbycs.com`, on Tailscale Personal, with MFA enabled before enrollment.
- T480: always on, on AC power, and retained local-console access.
- T16: full access to explicitly approved T480 services needed to build the Forex repository.
- iPhone: read-only access to the status-only dashboard and a cellular-network connectivity test. It does not receive RDP, SSH, database, n8n, Ollama, Docker, or administrative access.
- No router port forwards, public DNS, Cloudflare Tunnel, exit node, subnet router, or public service publication.

## Ordered work package

1. Capture a redacted preflight: M5 proof, T16-to-T480 LAN recovery path, physical/local-console recovery availability, Tailscale account ownership/MFA, intended device inventory, and the exact approved T16 services. Do not record credentials, IP addresses, or device keys.
2. Review security-sweep remediation as separate decision records. In particular, do not leave a publicly reachable PostgreSQL route merely because T16 needs development access. Any Windows upgrade, BitLocker, password-policy, SSH, RDP, port-proxy, or firewall change needs its own approval.
3. With explicit approval, install and enroll the official Tailscale clients on T480 and T16. Confirm both are the intended devices. Preserve the LAN SSH control path as recovery.
4. Define the tailnet policy before enabling useful service access. Do not retain the default allow-all rule. Allow the T16 only to the T480 ports/services the owner has approved for Forex development. Use standard Windows OpenSSH with keys; do not treat Tailscale SSH as a Windows server feature.
5. With explicit approval, enroll the iPhone. Identify its tailnet device identity, then make a device-specific policy that permits only the status dashboard port. A rule whose source is `chris@successbycs.com` is not sufficient: it covers every device owned by that user, including the T16. The dashboard itself must remain status-only and contain no controls, credentials, raw logs, or sensitive data.
6. Validate from an external network. Use T16 for RDP, key-based OpenSSH, and each approved development service. Turn off Wi-Fi on the iPhone and use cellular data to retrieve only the dashboard. Record both successful and denied connections without retaining sensitive endpoints or data.
7. Confirm no public ingress exists. Inspect router forwarding and tailnet route/public-DNS settings, and document the resolution of the existing PostgreSQL port-proxy/firewall exposure separately.
8. After M5's restart proof, obtain explicit restart approval; verify the T480 reconnects to the tailnet and its approved services return. Disable/revoke the iPhone in the tailnet administration console and verify dashboard access is denied. Produce a redacted owner runbook covering loss of phone, loss of T16, Tailscale account recovery, local-console recovery, and how to revoke a device.

## Approval gates

Ask separately before each of these actions:

1. Installing/enrolling Tailscale on T480 and T16.
2. Applying the reviewed tailnet policy.
3. Installing/enrolling Tailscale on the iPhone.
4. Each Windows firewall, OpenSSH, RDP, port-proxy, or security-remediation change.
5. Any restart or any device revocation/disable test.

Do not record passwords, keys, private IP addresses, unredacted service output, or cellular details in the milestone ledger or repository evidence.
