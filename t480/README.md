# T480 operations contract

This directory defines the fixed operations that a remote automation client may perform against the T480 AI Lab.

It is deliberately **not** a general remote-shell interface. The catalog and `../scripts/t480_adapter.py` contain a fixed allowlist; neither accepts a shell command, script, or arbitrary remote command arguments. `submit-transcription-folder` is the narrow exception for an explicitly operator-selected local Windows folder: its implementation accepts that one local path, transfers only direct portable-name MP4 files to a fixed private inbox, and invokes only fixed adapter operations. Mutating operations require explicit approval.

This MVP adopts the Autonomous Framework's adapter and tool-registry conventions. It is not yet an Autonomous Framework backport. Connection details belong in environment variables or SSH configuration, never in this repository.

## Initial operations

- `health` — Windows hostname, operating system, and installed memory.
- `storage` — filesystem capacity and free space.
- `health_dashboard_firewall_status` — inspect the fixed private-LAN TCP 8080 dashboard firewall rule.
- `health_dashboard_firewall_enable` — create or repair the fixed private-LAN TCP 8080 dashboard firewall rule; requires explicit approval.
- `windows_restart` — schedule a controlled Windows restart; requires explicit approval.
- `power_policy_status` — inspect active Windows sleep, hibernation, and lid-close policy.
- `power_policy_ac_always_on` — prevent sleep/hibernation and ignore lid close while on AC power; battery behaviour is unchanged; requires explicit approval.
- `m5_maintenance_preflight` — capture non-secret maintenance readiness, including update/BIOS/power state and private lab health.
- `m5_boot_startup_compatibility` — inspect current WSL distribution visibility and startup-task context before boot-task changes.
- `m5_boot_system_wsl_probe` — temporary, self-cleaning Local System WSL visibility test; requires explicit approval.
- `m5_boot_s4u_wsl_probe` — temporary, self-cleaning passwordless S4U WSL visibility test; requires explicit approval.
- `wsl_status` — WSL state and installed distributions.
- `docker_status` — Docker/Compose availability inside Ubuntu.
- `docker_preflight` — potentially conflicting Docker/container-runtime packages inside Ubuntu.
- `docker_install_diagnostics` — package-source and package-manager evidence after an installation failure.
- `docker_repository_probe` — reachability of Docker's signed repository.
- `wsl_stdin_probe` — safe validation of the quote-free WSL script transport.
- `startup_status` — inspect the Windows sign-in task for the private n8n lab stack.
- `startup_enable` — create or update the Windows sign-in task that starts Ubuntu, Docker, PostgreSQL, n8n, and the status-only dashboard and keeps WSL alive; requires explicit approval.
- `startup_run` — start that task immediately and check the local n8n health endpoint; requires explicit approval.
- `startup_diagnostics` — inspect the startup task result and its non-secret local log.
- `startup_disable` — remove that Windows sign-in task; requires explicit approval.
- `docker_runtime_evidence` — active service, package, Engine, Compose, and daemon access in a fresh session.
- `docker_hello_world` — real-container M1 proof; requires explicit approval.
- `ollama_embeddings_status` — private Ollama container and installed embedding models.
- `ollama_embeddings_install` — start private Ollama and install `bge-m3` and `mxbai-embed-large`; requires explicit approval.
- `ollama_embeddings_diagnostics` — non-secret completion or failure detail for the model installation.
- `m2_preflight` — capacity, runtime, deployment-path, and existing-container checks before M2.
- `m2_deploy` — controlled M2 clone, local-secret generation, image pull, and stack startup; requires explicit approval.
- `m2_deploy_diagnostics` — non-secret Compose, image, and container checks after a failed M2 deployment.
- `lab_services_start` — start the existing private PostgreSQL and n8n services plus the status-only dashboard; requires explicit approval.
- `lab_health` — read-only check of Docker, required service health, PostgreSQL query and pgvector extension, n8n and health-dashboard endpoints, optional running Ollama, and capacity.
- `lab_runtime_diagnostics` — inspect container status, available memory, and recent private runtime logs.
- `m2_latest_evidence_manifest` — reverify the newest M2 evidence bundle and return its fingerprint.
- `repository_update` — fast-forward a clean existing T480 checkout to `origin/main`; requires explicit approval.
- `repository_status` — show the fixed T480 lab checkout file status and local/fetched revisions without changing it.
- `repository_diff` — show only the local adapter-contract diff before a controlled checkout update.
- `repository_repair` — back up only corrupt zero-byte Git objects and fast-forward a clean repaired lab checkout; requires explicit approval.
- `repository_restore_corrupt_contract_files` — restore only the three known zero-byte adapter-contract files from fetched origin/main, then fast-forward; requires explicit approval.
- `repository_finalize_corrupt_contract_restore` — align Git metadata after the verified three-file restoration without changing working files; requires explicit approval.
- `forex_deploy` — deploy the reviewed hash-pinned Forex revision to its fixed T480 checkout; requires explicit approval.
- `forex_stage_m1_evidence` — hash-check and stage only the reviewed M1 capture for the fixed M2 import; requires explicit approval.
- `m3_recovery_proof` — run the isolated M3 synthetic database backup and restore drill; requires explicit approval.
- `m3_latest_evidence_manifest` — reverify the newest M3 recovery evidence bundle and return its fingerprint.
- `transcription_preflight` — inspect the fixed private MP4 transcriber checkout, cache/image readiness, and transient inbox state.
- `transcription_diagnostics` — inspect transcriber containers, inbox, and the latest job metadata after an interruption or failure.
- `transcription_completed_hashes` — inspect completed input SHA-256 values to make a resumed folder submission idempotent.
- `transcription_cleanup_completed_inbox` — remove only temporary inbox copies that exactly match successfully completed job hashes; requires explicit approval.
- `transcription_export_prepare` — prepare only completed review-required job folders in the fixed private T480 Windows export directory; requires explicit approval.
- `transcription_deploy` — clone or fast-forward the fixed private transcriber checkout, create local-only directories, and build its CPU-only image; requires explicit approval.
- `transcription_prepare` — rebuild the fixed private transcriber image and local-only directories if necessary; requires explicit approval.
- `transcription_windows_staging_prepare` — verify the fixed private Windows OpenSSH staging directory is empty before a media transfer; requires explicit approval.
- `transcription_model_prefetch` — explicitly cache the approved faster-whisper `base` model locally without handling media; requires explicit approval.
- `transcription_process_next` — process exactly one queued MP4 through the fixed one-shot worker and remove only its successful temporary inbox copy; requires explicit approval.
- `transcription_process_existing_inbox` — recover exactly one retained inbox MP4 after an interrupted submission; requires explicit approval.
- `docker_install` — install Docker Engine and Compose; requires explicit approval.

## MP4 transcription folder flow

The transcriber is a separate private repository at `/home/chris/projects/mp4-to-transcript`; it does not join, start, or duplicate this lab's PostgreSQL, n8n, or Ollama services. Its CPU-only container starts only for one requested video and exits after that job.

After `transcription_deploy`, `transcription_model_prefetch`, and a successful `transcription_preflight`, an operator may submit a Windows Explorer folder:

```bash
python3 scripts/t480_adapter.py submit-transcription-folder \
  --source-folder 'C:\Users\chris\Videos\To Transcribe' --approve
```

The adapter uses the existing Windows OpenSSH client, key authentication, and strict host-key checking. It sorts direct MP4 files by filename; skips sources whose SHA-256 already has a successful T480 job; uploads one to a fixed private Windows staging directory; moves that temporary copy into the fixed T480 inbox with a governed operation; invokes `transcription_process_next`; and continues only after success. The Windows originals are neither moved nor deleted. If a remote session ends between jobs, a later submission safely resumes from the first source whose SHA-256 lacks a successful job. Temporary inbox copies are deleted only when their SHA-256 exactly matches a completed job. `pull-transcription-outputs --approve` retrieves completed review artefacts only to the fixed local folder `C:\Users\chris\Videos\Transcripts`, using the original MP4 filename without its extension as the folder name; `job.json` retains the immutable job ID. No arbitrary download path is enabled.

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
python3 scripts/t480_adapter.py Healthcheck
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
