# M6 execution prompt — governed n8n upgrade

You are operating the private T480 AI Lab from the T16 workstation. Execute M6 — governed n8n upgrade proven.

## Outcome

Upgrade the existing n8n service from the vulnerable `1.118.1` image to a reviewed, immutable-digest-pinned `1.x` image at version `1.121.0` or later. Establish repeatable detection and upgrade controls. The UI notification is not permission to update automatically.

## Safety boundaries

- Keep n8n loopback-only. Do not expose its UI, API, webhook, or form endpoints to the network.
- Use official n8n release notes, security advisories, and image references. Do not use `latest` or an unpinned tag.
- Do not jump to n8n 2.x in this milestone. A major-version upgrade requires a separate reviewed milestone.
- Before changing n8n, create and independently verify a fresh PostgreSQL backup. Record the prior image digest as a rollback reference.
- Do not assume an n8n database migration can be safely downgraded. If validation fails after migration, stop, preserve evidence, and use the approved recovery process rather than blindly recreating the prior container.
- The adapter must accept only reviewed target identifiers defined in repository configuration; it must not accept arbitrary commands, images, tags, or digests from callers.
- Every image pull, container recreation, workflow import/activation, or rollback decision requires explicit approval.
- Use synthetic workflow data only for proof. Never log or commit credentials, customer data, encryption keys, database passwords, or API keys.

## Required execution order

1. Capture installed version, image digest, current health, port binding, release notes, advisory applicability, breaking-change assessment, and proposed target digest.
2. Create and independently verify a new PostgreSQL backup. Record backup fingerprint, rollback image reference, free disk capacity, and pre-upgrade service health.
3. Implement and test a fixed `n8n_upgrade` operation: it verifies preflight, pulls only the reviewed target, recreates only n8n, waits for health, and emits non-secret evidence. Also implement a read-only update/advisory status operation and a recurring reporting control that does not auto-install anything.
4. With explicit approval, execute the upgrade and verify n8n's version, exact image digest, loopback binding, PostgreSQL readiness, and n8n health endpoint.
5. Through the governed n8n adapter, run a bounded synthetic workflow. Capture the raw T480 output and independently verify the evidence bundle.
6. If validation fails, stop and apply the recovery decision tree; do not automatically downgrade a potentially migrated database.
7. Record all passing acceptance checks in the local ledger only after the independent verifier passes.

## Success criteria

- The live n8n image is a reviewed, pinned 1.x version at least `1.121.0`.
- Pre-upgrade backup and rollback information are real and independently verified.
- n8n remains private and its real workflow path works after the upgrade.
- Future update discovery is automated as reporting only; upgrades still require a human decision and explicit approval.
