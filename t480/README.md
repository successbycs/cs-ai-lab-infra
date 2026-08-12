# T480 operations contract

This directory defines the fixed operations that a remote automation client may perform against the T480 AI Lab.

It is deliberately **not** a general remote-shell interface. The catalog and `../scripts/t480_adapter.py` contain a fixed allowlist; neither accepts a shell command, script, or command arguments. Mutating operations require explicit approval.

This MVP adopts the Autonomous Framework's adapter and tool-registry conventions. It is not yet an Autonomous Framework backport. Connection details belong in environment variables or SSH configuration, never in this repository.

## Initial operations

- `health` — Windows hostname, operating system, and installed memory.
- `storage` — filesystem capacity and free space.
- `wsl_status` — WSL state and installed distributions.
- `docker_status` — Docker/Compose availability inside Ubuntu.
- `docker_preflight` — potentially conflicting Docker/container-runtime packages inside Ubuntu.
- `docker_install_diagnostics` — package-source and package-manager evidence after an installation failure.
- `docker_repository_probe` — reachability of Docker's signed repository.
- `wsl_stdin_probe` — safe validation of the quote-free WSL script transport.
- `startup_status` — inspect the Windows sign-in task for the private n8n lab stack.
- `startup_enable` — create or update the Windows sign-in task that starts Ubuntu, Docker, PostgreSQL, and n8n; requires explicit approval.
- `startup_disable` — remove that Windows sign-in task; requires explicit approval.
- `docker_runtime_evidence` — active service, package, Engine, Compose, and daemon access in a fresh session.
- `docker_hello_world` — real-container M1 proof; requires explicit approval.
- `ollama_embeddings_status` — private Ollama container and installed embedding models.
- `ollama_embeddings_install` — start private Ollama and install `bge-m3` and `mxbai-embed-large`; requires explicit approval.
- `ollama_embeddings_diagnostics` — non-secret completion or failure detail for the model installation.
- `m2_preflight` — capacity, runtime, deployment-path, and existing-container checks before M2.
- `m2_deploy` — controlled M2 clone, local-secret generation, image pull, and stack startup; requires explicit approval.
- `m2_deploy_diagnostics` — non-secret Compose, image, and container checks after a failed M2 deployment.
- `lab_services_start` — start the existing private PostgreSQL and n8n services; requires explicit approval.
- `m2_latest_evidence_manifest` — reverify the newest M2 evidence bundle and return its fingerprint.
- `repository_update` — fast-forward a clean existing T480 checkout to `origin/main`; requires explicit approval.
- `m3_recovery_proof` — run the isolated M3 synthetic database backup and restore drill; requires explicit approval.
- `m3_latest_evidence_manifest` — reverify the newest M3 recovery evidence bundle and return its fingerprint.
- `docker_install` — install Docker Engine and Compose; requires explicit approval.

## MVP adapter

The adapter follows the Autonomous Framework's first-class tool pattern: it has a small registry entry, preflight, requirements description, execute, verify, and structured evidence. It starts a local T16 PowerShell child process, uses the T16 Windows OpenSSH client from that process, and then invokes the fixed WSL action for the selected operation on the T480. This reuses the T16 Windows SSH configuration rather than a separate WSL SSH configuration. It reads `T480_SSH_TARGET` from the environment or from the ignored `.env.t480.local` file, and assumes key authentication and host-key verification are already configured.

```bash
T480_SSH_TARGET=t480 python3 scripts/t480_adapter.py describe-requirements
T480_SSH_TARGET=t480 python3 scripts/t480_adapter.py preflight
T480_SSH_TARGET=t480 python3 scripts/t480_adapter.py execute --operation health
T480_SSH_TARGET=t480 python3 scripts/t480_adapter.py execute --operation docker_install --approve
T480_SSH_TARGET=t480 python3 scripts/t480_adapter.py verify --operation docker_install
```

When `.env.t480.local` contains `T480_SSH_TARGET`, the environment prefix is unnecessary. This is the simplest local use:

```bash
python3 scripts/t480_adapter.py preflight
```

The fourth command changes the T480: it installs Docker and adds the fixed `chris` Ubuntu user to the Docker group. It deliberately uses `wsl.exe -u root` so it never requests, stores, or automates a Linux password. A fresh Ubuntu session is required after installation for the new Docker-group membership to take effect.

The PowerShell process is deliberately non-interactive and its output returns to Codex; it does not open a separate visible terminal window, because Codex cannot reliably control or receive output from a detached GUI window. The adapter is a safety boundary for automation on the T16, not a general hardening boundary for the T480 Windows account. Anyone with interactive access to that Windows account can still run commands directly.

For the current broad bootstrap phase, use the reusable [adapter execution prompt](prompts/adapter-execution.md). It applies the Autonomous Framework's preflight, approval, verification, and evidence model while the execution surface is intentionally wider than the future named-operation adapter.

Track real-machine progress with the lightweight [milestone system](milestones.md). It keeps milestone definitions in Git and local evidence outside Git.

For a durable handoff after a paused session, start with [the next-session note](next-session.md). It records the next approved operational step without storing secrets.

Process improvements discovered while operating the real machines are recorded in the tracked [execution process log](process-log.md), without private connection details or raw host output.

Each adapter invocation also appends local audit metadata to the ignored `.t480-execution.local.jsonl` file: operation, approval state, UTC timing, exit status, and hashes and byte counts for stdout/stderr. It intentionally does not retain raw host output or connection details.

## Security rules

- Use SSH key authentication; never put the T480 Windows password in `.env`.
- Keep `StrictHostKeyChecking` enabled.
- Do not add a `command`, `script`, or free-form PowerShell argument to the adapter.
- Treat command output as operational data: retain it locally for audit, but do not commit it when it contains personal/device details.
