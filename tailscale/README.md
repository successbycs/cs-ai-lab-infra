# Governed Tailscale adapter

`scripts/tailscale_adapter.py` administers the owner-controlled Tailscale tailnet through fixed operations. It cannot execute arbitrary API calls, configure router forwarding, create public ingress, advertise routes, or enable an exit node.

## Credential prerequisite

Create a Tailscale OAuth client and copy [the local configuration template](.env.tailscale.local.example) to the repository root as `.env.tailscale.local`. Keep it ignored by Git and readable only by the local operator. Use separate least-privilege OAuth clients where practical:

- Audit: `devices:core:read`, `devices:routes:read`, `policy_file:read`, and `devices:posture_attributes:read`.
- Policy apply: `policy_file`, `devices:core:read`, and `devices:posture_attributes:read`.
- Device approval/revocation: `devices:core`.

The adapter obtains a short-lived OAuth access token at runtime; it does not accept a Tailscale API key or print credentials.

## Commands

```bash
python3 scripts/tailscale_adapter.py describe-requirements
python3 scripts/tailscale_adapter.py preflight
python3 scripts/tailscale_adapter.py list-devices
python3 scripts/tailscale_adapter.py inspect-policy
python3 scripts/tailscale_adapter.py validate-policy --policy-file tailscale/policies/reviewed-policy.hujson
python3 scripts/tailscale_adapter.py apply-policy --policy-file tailscale/policies/reviewed-policy.hujson --approve
python3 scripts/tailscale_adapter.py set-device-authorization --device-id DEVICE_ID --deauthorize --approve
```

`apply-policy` always validates the exact reviewed file first. `set-device-authorization` can approve or revoke a device but never deletes it. All mutation attempts require `--approve`, and the local execution log stores only timestamps, operation names, output sizes, and hashes.

Tailscale policy changes are version-controlled HuJSON under `tailscale/policies/`; validate them before applying. Do not use a user-wide source rule for the iPhone’s read-only dashboard access, because it would cover every device owned by that user. Use a device-specific selector after the T16 and iPhone identities are confirmed.
