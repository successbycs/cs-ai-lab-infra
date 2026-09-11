# Penpot operator runbook

Run T480 commands from the repository root through the fixed adapter unless
performing the explicitly interactive account step at the T480 console.

## Deploy, start, health, and stop

```bash
python3 scripts/t480_adapter.py execute --operation penpot_preflight
python3 scripts/t480_adapter.py execute --operation penpot_deploy --approve
python3 scripts/t480_adapter.py execute --operation penpot_health
python3 scripts/t480_adapter.py execute --operation penpot_start --approve
python3 scripts/t480_adapter.py execute --operation penpot_disable --approve
```

`penpot_disable` runs Compose `down` without `--volumes`; data is retained.
Never use `down -v` for routine work.

## Owner and user access

No account ships with the deployment. On the T480 console, create Chris's
owner account without placing credentials in shell history:

```bash
cd /home/chris/projects/cs-ai-lab-infra
./penpot/scripts/create-profile.sh
```

Use a unique password of at least 20 characters stored in Chris's password
manager. Penpot does not expose a separate global-admin role in this setup;
host/CLI administration remains separate from the owner design identity.

Keep registration disabled. Create each additional human or MCP service
account with the same interactive command. With SMTP disabled, invitations are
not an approved provisioning path. Give the MCP identity membership only in
teams/projects it should edit.

## Backup

```bash
python3 scripts/t480_adapter.py execute --operation penpot_backup --approve
```

Each ignored `penpot/backups/<UTC>/` bundle contains a PostgreSQL custom dump,
asset archive, image list, revision, metadata, and checksums. It never contains
the live environment/master secret. Default local retention is 14 days.
Existing off-host backup policy must copy both the bundle and a separately
protected recovery record for
`/home/chris/.config/cs-ai-lab/penpot.env`; do not place that secret in the
bundle or Git.

Verify the newest backup by restoring into temporary isolated Docker volumes:

```bash
python3 scripts/t480_adapter.py execute --operation penpot_restore_test --approve
```

The test verifies checksums, restores PostgreSQL and assets, queries restored
profile/file counts, and removes only its timestamped test container/volumes.

## Live restore

Live restore is destructive and must have Chris's explicit approval. Confirm
the exact bundle and protected environment record first. Then at the T480:

```bash
cd /home/chris/projects/cs-ai-lab-infra
export PENPOT_ENV_FILE=/home/chris/.config/cs-ai-lab/penpot.env
source penpot/scripts/lib.sh
bundle=penpot/backups/YYYYMMDDTHHMMSSZ
(cd "$bundle" && sha256sum -c SHA256SUMS)
compose stop penpot-frontend penpot-mcp penpot-exporter penpot-backend
compose exec -T penpot-postgres pg_restore \
  --username penpot --dbname penpot --clean --if-exists \
  --no-owner --no-privileges < "$bundle/penpot.dump"
compose run --rm --no-deps -T penpot-frontend \
  sh -c 'find /opt/data/assets -mindepth 1 -delete; tar -C /opt/data/assets -xzf -' \
  < "$bundle/assets.tar.gz"
compose up -d --wait --wait-timeout 300
./penpot/scripts/health.sh
```

Use only a bundle from the matching master-secret lineage. If the secret is
lost, existing sessions/invitations and encrypted values may be unrecoverable.

## Upgrade and rollback

1. Review Penpot release notes, migrations, and security advisories.
2. Change all four Penpot image tags/digests together in `compose.yaml`; update
   PostgreSQL/Valkey separately only when compatibility is confirmed.
3. Commit and deploy the reviewed configuration to the clean T480 checkout.
4. Run `penpot_backup`, then `compose pull`. Pulling does not alter containers.
5. Record `compose images`, start with `compose up -d --wait`, then run health,
   login, persistence, backup/restore, and MCP verification.

If pull/start/verification fails, stop writers, return the checkout to the
previous reviewed commit, run `compose up -d --wait`, and restore the pre-upgrade
bundle if any database migration ran. Image rollback without database rollback
is not sufficient after a schema migration.

The non-destructive rollback-path drill is:

```bash
python3 scripts/t480_adapter.py execute --operation penpot_rollback_test --approve
```

It attempts a deliberately invalid candidate pull, proves live container IDs
were unchanged, reapplies the pinned configuration, and health-checks it.

## Persistence and resources

```bash
python3 scripts/t480_adapter.py execute --operation penpot_persistence_test --approve
python3 scripts/t480_adapter.py execute --operation penpot_resource_report
```

The first records profile/file counts, restarts only the Penpot project, and
proves counts survive. The second records point-in-time CPU, memory, volume,
and filesystem use. Investigate if Windows free space approaches 15 GiB, WSL
memory pressure affects existing services, or sustained export work reaches
the configured limits.

## Token rotation and emergency disablement

Token rotation is described in [MCP.md](MCP.md). For a suspected design-token
leak: disconnect the active file, revoke the key in Penpot, terminate the SSH
forward, and run `penpot_disable --approve`. This leaves recoverable volumes.
Do not delete volumes as incident response.

## Internet-facing release gate

Chris must approve all of the following before any non-loopback bind:

- private/public audience and threat model;
- hostname/DNS and ingress path;
- trusted reverse proxy and certificate automation;
- HTTPS-only `PENPOT_PUBLIC_URI` and secure-session cookies;
- authentication, invitation/SMTP, account lifecycle, and rate-limit policy;
- Windows/private-network firewall scope and independent reachability test;
- off-host encrypted backup retention plus a successful full restore;
- monitoring/log review and capacity budget;
- MCP multi-user risk, service-account/project membership, and revocation test.

No router/firewall/DNS/ingress action is part of the localhost deployment.
