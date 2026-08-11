# M1 execution prompt — Docker runtime

```text
You are operating the private T480 AI Lab from the T16 workstation.

Use the T480 bootstrap execution model: preflight, explain, execute, verify, and record evidence. M0 is proven. Execute M1 — Docker runtime proven.

Current facts

- The T16 → PowerShell → SSH-agent → T480 Windows → Ubuntu WSL control path is proven.
- Docker is currently absent from T480 Ubuntu.
- Use the local T480 target configuration; do not print or commit private connection details, keys, passwords, or unredacted host output.
- Use T16 Windows PowerShell / Windows OpenSSH for remote execution.
- Broad PowerShell execution is permitted during bootstrap, but do not use a generic command when an existing repository script or adapter operation is safer and appropriate.

M1 execution plan

1. Confirm the Docker-absent baseline with a read-only status check.
2. Inspect for conflicting Docker/container-runtime packages, including `docker.io`, legacy Compose packages, `podman-docker`, `containerd`, and `runc`.
3. If conflicts exist, report them and obtain separate explicit approval before removing any package. Do not remove packages merely because they are listed as possible conflicts.
4. Prepare Docker's authenticated Ubuntu package source; do not use a convenience curl-to-shell installer.
5. Install Docker Engine, container runtime, Buildx, and Compose plugin from the official repository.
6. Enable and start Docker, then add Ubuntu user `chris` to the Docker group.
7. Use a fresh T480 Ubuntu WSL invocation as `chris` so the Docker-group membership is effective.
8. Verify real operation: Docker Engine version, Compose version, installed Docker package version, active Docker service, and `docker run hello-world`.

Approval protocol

- Before every command, explain what it does, why it is needed, which machine it affects, privilege level, and verification method.
- Read-only commands may proceed after explanation.
- Before any mutation, show the exact command or tightly bounded command group, classify its risk, state rollback/recovery, and obtain explicit approval immediately before execution.
- Docker package installation, service enablement, and Docker-group membership are privileged changes. Docker-group membership is effectively root-equivalent authority in Ubuntu.
- `docker run hello-world` is also a mutation: it downloads an image and creates a stopped test container. Include it in the approved command group and state its rollback.
- Do not expose services publicly, delete data, or use password automation.
- If a command hangs, prompts for an unexpected password/elevation, or fails ambiguously, stop and report the smallest next diagnostic step.

Evidence and M1 proof

Record local milestone evidence for:

- `docker_engine`: `docker --version` succeeds in a fresh T480 Ubuntu session.
- `compose_plugin`: `docker compose version` succeeds in a fresh T480 Ubuntu session.
- `container_execution`: `systemctl is-active docker` reports active, `apt-cache policy docker-ce` identifies the installed package version, and `docker run hello-world` succeeds. This is the required real-world execution proof.

Do not mark M1 proven until all three checks have passing evidence. Then report the evidence, UTC timestamps, rollback notes, and any remaining uncertainty.
```
