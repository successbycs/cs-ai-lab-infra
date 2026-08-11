# T480 operations contract

This directory defines the read-only operations that a remote automation client may perform against the T480 AI Lab.

It is deliberately **not** a general remote-shell interface. The catalog contains fixed, inspect-only operations. Installations, configuration changes, restarts, deployments, backups, and deletions remain explicit operator-approved actions.

The Autonomous Framework backport consumes the same contract through its `T480Adapter`. Connection details belong in environment variables or SSH configuration, never in this repository.

## Initial operations

- `health` — Windows hostname, operating system, and installed memory.
- `storage` — filesystem capacity and free space.
- `wsl_status` — WSL state and installed distributions.
- `docker_status` — Docker/Compose availability inside Ubuntu.

## Security rules

- Use SSH key authentication; never put the T480 Windows password in `.env`.
- Keep `StrictHostKeyChecking` enabled.
- Do not expose a `command`, `script`, or free-form PowerShell argument to an AI model.
- Treat command output as operational data: retain it locally for audit, but do not commit it when it contains personal/device details.
