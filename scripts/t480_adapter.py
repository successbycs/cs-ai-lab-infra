#!/usr/bin/env python3
"""Governed SSH/WSL adapter for the T480 AI Lab.

Only the operation identifiers in t480/command-catalog.json are executable.
This program intentionally provides no argument for a shell, PowerShell, or SSH
command. Approval is an operator-facing audit signal; it is not a substitute
for the human approval required by the operating process.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOL_ID = "t480_wsl_lab"
SSH_TARGET_ENV = "T480_SSH_TARGET"
LOCAL_CONFIG_PATH = Path(__file__).resolve().parent.parent / ".env.t480.local"
EXECUTION_LOG_PATH = Path(__file__).resolve().parent.parent / ".t480-execution.local.jsonl"

DOCKER_INSTALL_SCRIPT = """set -euo pipefail
apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
printf 'Types: deb\\nURIs: https://download.docker.com/linux/ubuntu\\nSuites: %s\\nComponents: stable\\nArchitectures: %s\\nSigned-By: /etc/apt/keyrings/docker.asc\\n' "${UBUNTU_CODENAME:-$VERSION_CODENAME}" "$(dpkg --print-architecture)" > /etc/apt/sources.list.d/docker.sources
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
usermod -aG docker chris
"""

# The command text is private to this adapter. Callers choose an operation ID,
# never a command or arguments.
OPERATIONS: dict[str, dict[str, Any]] = {
    "health": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$os = Get-CimInstance Win32_OperatingSystem; "
            "$computer = Get-CimInstance Win32_ComputerSystem; "
            "[pscustomobject]@{ hostname = $env:COMPUTERNAME; os = $os.Caption; "
            "version = $os.Version; memory_gib = [math]::Round($computer.TotalPhysicalMemory / 1GB, 1) } "
            "| ConvertTo-Json -Compress"
        ),
    },
    "storage": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "Get-CimInstance Win32_LogicalDisk -Filter 'DriveType = 3' | "
            "Select-Object DeviceID, @{Name='size_gib'; Expression={[math]::Round($_.Size / 1GB, 1)}}, "
            "@{Name='free_gib'; Expression={[math]::Round($_.FreeSpace / 1GB, 1)}} | ConvertTo-Json -Compress"
        ),
    },
    "wsl_status": {
        "approval_required": False,
        "command": "$ErrorActionPreference = 'Stop'; wsl.exe --status; wsl.exe --list --verbose",
    },
    "docker_status": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "wsl.exe -d Ubuntu -- bash -lc 'docker --version && docker compose version && docker info >/dev/null && echo docker-daemon-ok'"
        ),
    },
    "docker_preflight": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "wsl.exe -d Ubuntu -- bash -lc 'dpkg-query -W docker.io docker-compose docker-compose-v2 docker-doc "
            "docker-buildx podman-docker containerd runc 2>/dev/null || true'"
        ),
    },
    "docker_install_diagnostics": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "wsl.exe -d Ubuntu -- bash -lc 'set -e; "
            "echo ---docker-source---; test -f /etc/apt/sources.list.d/docker.sources && "
            "cat /etc/apt/sources.list.d/docker.sources || echo absent; "
            "echo ---docker-packages---; apt-cache policy docker-ce docker-ce-cli containerd.io || true; "
            "echo ---recent-apt-log---; test -f /var/log/apt/term.log && tail -n 80 /var/log/apt/term.log || true'"
        ),
    },
    "docker_repository_probe": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "wsl.exe -d Ubuntu -- curl --fail --silent --show-error --location --max-time 20 "
            "--output /dev/null --write-out 'HTTP %{http_code}' https://download.docker.com/linux/ubuntu/gpg"
        ),
    },
    "wsl_stdin_probe": {
        "approval_required": False,
        "wsl_script": "printf 'wsl-stdin-ok\\n'\n",
    },
    "startup_status": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$task = Get-ScheduledTask -TaskName 'CS AI Lab Start' -ErrorAction SilentlyContinue; "
            "if ($null -eq $task) { '[{\"present\":false}]' } else { "
            "$info = Get-ScheduledTaskInfo -TaskName 'CS AI Lab Start'; "
            "[pscustomobject]@{ present = $true; state = $task.State.ToString(); "
            "last_run_time = $info.LastRunTime.ToUniversalTime().ToString('o'); "
            "last_task_result = $info.LastTaskResult } | ConvertTo-Json -Compress }"
        ),
    },
    "startup_enable": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$arguments = '-d Ubuntu -- bash -lc \"for attempt in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 2; done; "
            "docker info >/dev/null; cd /home/chris/projects/cs-ai-lab-infra; docker compose up -d n8n\"'; "
            "$action = New-ScheduledTaskAction -Execute 'wsl.exe' -Argument $arguments; "
            "$trigger = New-ScheduledTaskTrigger -AtLogOn; "
            "Register-ScheduledTask -TaskName 'CS AI Lab Start' -Action $action -Trigger $trigger "
            "-Description 'Starts T480 Ubuntu WSL, waits for Docker, and starts the private n8n lab stack at sign-in.' -Force | Out-Null; "
            "Get-ScheduledTask -TaskName 'CS AI Lab Start' | Select-Object TaskName,State | ConvertTo-Json -Compress"
        ),
    },
    "startup_disable": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "Unregister-ScheduledTask -TaskName 'CS AI Lab Start' -Confirm:$false -ErrorAction SilentlyContinue; "
            "'{\"removed\":true}'"
        ),
    },
    "docker_runtime_evidence": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "systemctl is-active docker\n"
            "apt-cache policy docker-ce | sed -n '1,4p'\n"
            "docker --version\n"
            "docker compose version\n"
            "docker info >/dev/null\n"
            "echo docker-daemon-ok\n"
        ),
    },
    "docker_hello_world": {
        "approval_required": True,
        "wsl_script": "set -euo pipefail\ndocker run --rm hello-world\n",
    },
    "ollama_embeddings_status": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "echo ---ollama-container---\n"
            "docker compose --profile ollama ps ollama\n"
            "if docker compose --profile ollama ps --status running --services | grep -qx ollama; then\n"
            "  echo ---ollama-models---\n"
            "  docker compose exec -T ollama ollama list || true\n"
            "else\n"
            "  echo ollama-not-running\n"
            "fi\n"
            "echo ---installation-job---\n"
            "if [ -f /home/chris/.local/state/cs-ai-lab/ollama-embeddings-install.pid ] && "
            "kill -0 \"$(cat /home/chris/.local/state/cs-ai-lab/ollama-embeddings-install.pid)\" 2>/dev/null; then\n"
            "  echo running\n"
            "else\n"
            "  echo not-running\n"
            "fi\n"
            "echo ---installation-log---\n"
            "test -f /home/chris/.local/state/cs-ai-lab/ollama-embeddings-install.log && "
            "tail -n 40 /home/chris/.local/state/cs-ai-lab/ollama-embeddings-install.log || echo absent\n"
        ),
    },
    "ollama_embeddings_install": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "state_dir=/home/chris/.local/state/cs-ai-lab\n"
            "mkdir -p \"$state_dir\"\n"
            "job_pid_file=\"$state_dir/ollama-embeddings-install.pid\"\n"
            "job_log_file=\"$state_dir/ollama-embeddings-install.log\"\n"
            "if [ -f \"$job_pid_file\" ] && kill -0 \"$(cat \"$job_pid_file\")\" 2>/dev/null; then\n"
            "  echo ollama-embeddings-install-already-running\n"
            "  exit 0\n"
            "fi\n"
            "nohup bash -c 'set -euo pipefail; cd /home/chris/projects/cs-ai-lab-infra; "
            "docker compose --profile ollama config --quiet; docker compose --profile ollama pull ollama; "
            "docker compose --profile ollama up -d --wait --wait-timeout 180 ollama; "
            "docker compose exec -T ollama ollama pull bge-m3; "
            "docker compose exec -T ollama ollama pull mxbai-embed-large' "
            ">\"$job_log_file\" 2>&1 &\n"
            "echo $! > \"$job_pid_file\"\n"
            "echo ollama-embeddings-install-started\n"
        ),
    },
    "ollama_embeddings_diagnostics": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "log_file=/home/chris/.local/state/cs-ai-lab/ollama-embeddings-install.log\n"
            "if [ -f \"$log_file\" ]; then\n"
            "  tail -n 80 \"$log_file\"\n"
            "else\n"
            "  echo no-ollama-embedding-install-log\n"
            "fi\n"
        ),
    },
    "m2_preflight": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "echo ---identity---\n"
            "whoami\n"
            "pwd\n"
            "echo ---capacity---\n"
            "df -h /\n"
            "echo ---docker---\n"
            "docker --version\n"
            "docker compose version\n"
            "echo ---deployment-prerequisites---\n"
            "command -v git\n"
            "command -v openssl\n"
            "echo ---deployment-path---\n"
            "if [ -d /home/chris/projects/cs-ai-lab-infra ]; then\n"
            "  echo present\n"
            "  git -C /home/chris/projects/cs-ai-lab-infra rev-parse --short HEAD 2>/dev/null || true\n"
            "else\n"
            "  echo absent\n"
            "fi\n"
            "echo ---existing-lab-containers---\n"
            "docker ps -a --filter label=com.docker.compose.project=cs-ai-lab --format '{{.Names}} {{.Status}}'\n"
        ),
    },
    "m2_deploy": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "repository_url='https://github.com/successbycs/cs-ai-lab-infra.git'\n"
            "deployment_root='/home/chris/projects/cs-ai-lab-infra'\n"
            "if [[ -e \"$deployment_root\" ]]; then\n"
            "  printf 'Refusing M2 deployment: target already exists: %s\\n' \"$deployment_root\" >&2\n"
            "  exit 4\n"
            "fi\n"
            "mkdir -p /home/chris/projects\n"
            "git clone --branch main --depth 1 \"$repository_url\" \"$deployment_root\"\n"
            "cd \"$deployment_root\"\n"
            "umask 077\n"
            "cp .env.example .env\n"
            "postgres_password=\"$(openssl rand -hex 32)\"\n"
            "n8n_encryption_key=\"$(openssl rand -hex 32)\"\n"
            "sed -i \"s/CHANGE_ME_TO_A_LONG_UNIQUE_PASSWORD/$postgres_password/\" .env\n"
            "sed -i \"s/CHANGE_ME_TO_A_LONG_RANDOM_VALUE/$n8n_encryption_key/\" .env\n"
            "chmod 600 .env\n"
            "./scripts/bootstrap.sh\n"
            "docker compose config --quiet\n"
            "docker compose pull\n"
            "docker compose up -d --wait --wait-timeout 180\n"
            "git rev-parse HEAD\n"
        ),
    },
    "m2_deploy_diagnostics": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "echo ---revision---\n"
            "git rev-parse --short HEAD\n"
            "echo ---env-permissions---\n"
            "stat -c '%a %n' .env\n"
            "echo ---compose-validation---\n"
            "docker compose config --quiet\n"
            "echo valid\n"
            "echo ---configured-images---\n"
            "docker compose config --images\n"
            "echo ---local-images---\n"
            "docker compose images\n"
            "echo ---containers---\n"
            "docker compose ps -a\n"
        ),
    },
    "lab_services_start": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "docker compose up -d --wait --wait-timeout 180 n8n\n"
            "docker compose ps n8n postgres\n"
        ),
    },
    "lab_runtime_diagnostics": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "echo ---compose-status---\n"
            "docker compose ps -a\n"
            "echo ---docker-memory---\n"
            "free -h\n"
            "echo ---n8n-logs---\n"
            "docker compose logs --tail 80 n8n\n"
            "echo ---postgres-logs---\n"
            "docker compose logs --tail 80 postgres\n"
            "echo ---ollama-logs---\n"
            "docker compose --profile ollama logs --tail 80 ollama\n"
        ),
    },
    "m2_latest_evidence_manifest": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "bundle_dir=\"$(find evidence/M2 -mindepth 1 -maxdepth 1 -type d -printf '%f\\n' | sort | tail -n 1)\"\n"
            "[[ -n \"$bundle_dir\" ]] || { printf 'No M2 evidence bundle exists.\\n' >&2; exit 4; }\n"
            "bundle_path=\"evidence/M2/$bundle_dir\"\n"
            "./scripts/verify-m2-evidence.sh \"$bundle_path\"\n"
            "sha256sum \"$bundle_path/SHA256SUMS\"\n"
        ),
    },
    "repository_update": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "repository_root='/home/chris/projects/cs-ai-lab-infra'\n"
            "cd \"$repository_root\"\n"
            "git diff --quiet || { printf 'Refusing update: tracked working-tree changes exist.\\n' >&2; exit 4; }\n"
            "git diff --cached --quiet || { printf 'Refusing update: staged changes exist.\\n' >&2; exit 4; }\n"
            "test -z \"$(git status --porcelain --untracked-files=normal)\" || { printf 'Refusing update: untracked files exist.\\n' >&2; exit 4; }\n"
            "git fetch origin main\n"
            "git merge --ff-only origin/main\n"
            "git rev-parse HEAD\n"
        ),
    },
    "m3_recovery_proof": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "./scripts/m3-recovery-proof.sh\n"
        ),
    },
    "m3_latest_evidence_manifest": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "bundle_dir=\"$(find evidence/M3 -mindepth 1 -maxdepth 1 -type d -printf '%f\\n' | sort | tail -n 1)\"\n"
            "[[ -n \"$bundle_dir\" ]] || { printf 'No M3 evidence bundle exists.\\n' >&2; exit 4; }\n"
            "bundle_path=\"evidence/M3/$bundle_dir\"\n"
            "./scripts/verify-m3-recovery-evidence.sh \"$bundle_path\"\n"
            "sha256sum \"$bundle_path/SHA256SUMS\"\n"
        ),
    },
    "docker_install": {
        "approval_required": True,
        "wsl_script": DOCKER_INSTALL_SCRIPT,
        "wsl_user": "root",
    },
}

CATALOG_PATH = Path(__file__).resolve().parent.parent / "t480" / "command-catalog.json"


def validate_contract() -> None:
    """Refuse execution if the published contract and adapter have diverged."""
    with CATALOG_PATH.open(encoding="utf-8") as catalog_file:
        catalog = json.load(catalog_file)
    catalog_ids = {operation["id"] for operation in catalog["operations"]}
    adapter_ids = set(OPERATIONS)
    if catalog_ids != adapter_ids:
        raise RuntimeError(
            "Adapter and command catalog operation IDs differ: "
            f"catalog={sorted(catalog_ids)}, adapter={sorted(adapter_ids)}"
        )


def requirements() -> dict[str, Any]:
    return {
        "tool_id": TOOL_ID,
        "description": "Run fixed, audited T480 Windows/WSL operations over SSH.",
        "requirements": [
            f"Set {SSH_TARGET_ENV}, or record it in the ignored {LOCAL_CONFIG_PATH.name} file.",
            "Configure SSH key authentication and verify the T480 host key before use.",
            "Ensure the Windows SSH account can run wsl.exe and access the Ubuntu distribution.",
            "Explicitly approve every mutating operation in the operator conversation before execution.",
        ],
        "commands": ["describe-requirements", "preflight", "execute", "verify"],
        "operations": [
            {"id": operation_id, "approval_required": details["approval_required"]}
            for operation_id, details in OPERATIONS.items()
        ],
    }


def ssh_command(target: str, powershell_command: str) -> list[str]:
    """Run Windows OpenSSH from T16 PowerShell, not a separate WSL SSH config."""
    encoded_remote_command = base64.b64encode(powershell_command.encode("utf-16-le")).decode("ascii")
    encoded_target = base64.b64encode(target.encode("utf-8")).decode("ascii")
    return [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "$target = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"
            f"{encoded_target}')); "
            "$remoteCommand = 'powershell.exe -NoProfile -NonInteractive "
            f"-EncodedCommand {encoded_remote_command}'; "
            "$sshArguments = @('-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', "
            "$target, $remoteCommand); & ssh.exe @sshArguments"
        ),
    ]


def wsl_bash_script_command(script: str, user: str | None = None) -> str:
    """Send an exact UTF-8 script to WSL without CRLF or nested-script issues."""
    encoded_script = base64.b64encode(script.encode("utf-8")).decode("ascii")
    user_argument = " -u root" if user == "root" else ""
    return (
        "$ErrorActionPreference = 'Stop'; "
        f"'{encoded_script}' | wsl.exe -d Ubuntu{user_argument} -- bash -c 'base64 -d | bash'"
    )


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def append_execution_log(command_name: str, operation_id: str | None, payload: dict[str, Any]) -> None:
    """Keep local audit metadata without retaining private host output."""
    result = payload.get("result") or payload.get("remote_check") or {}
    entry = {
        "logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool_id": TOOL_ID,
        "command": command_name,
        "operation": operation_id,
        "approval_required": payload.get("approval_required"),
        "approved": payload.get("approved"),
        "started_at": result.get("started_at"),
        "finished_at": result.get("finished_at"),
        "duration_ms": result.get("duration_ms"),
        "exit_code": result.get("exit_code"),
        "ok": payload.get("ok", result.get("ok")),
        "stdout_bytes": len(result.get("stdout", "")),
        "stderr_bytes": len(result.get("stderr", "")),
        "stdout_sha256": digest(result.get("stdout", "")),
        "stderr_sha256": digest(result.get("stderr", "")),
    }
    with EXECUTION_LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(entry, separators=(",", ":")) + "\n")


def run_command(command: list[str]) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    started_monotonic = time.monotonic()
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, SSH_TARGET_ENV: configured_target()},
    )
    finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if finished_at < started_at:
        finished_at = started_at
    return {
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": round((time.monotonic() - started_monotonic) * 1000),
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "ok": completed.returncode == 0,
    }


def configured_target() -> str:
    target = os.environ.get(SSH_TARGET_ENV, "").strip()
    if not target and LOCAL_CONFIG_PATH.is_file():
        for line in LOCAL_CONFIG_PATH.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{SSH_TARGET_ENV}="):
                target = line.partition("=")[2].strip()
                break
    if not target:
        raise RuntimeError(
            f"Set {SSH_TARGET_ENV} or add it to the ignored {LOCAL_CONFIG_PATH.name} file."
        )
    return target


def preflight() -> dict[str, Any]:
    try:
        target = configured_target()
    except RuntimeError as error:
        return {
            "tool_id": TOOL_ID,
            "local_checks": {"ssh_available": shutil.which("ssh") is not None, "ssh_target_configured": False},
            "ok": False,
            "error": str(error),
        }
    local_checks = {
        "powershell_available": shutil.which("powershell.exe") is not None,
        "windows_ssh_available": shutil.which("ssh.exe") is not None,
        "ssh_target_configured": bool(target),
    }
    payload: dict[str, Any] = {"tool_id": TOOL_ID, "local_checks": local_checks}
    if not all(local_checks.values()):
        payload["ok"] = False
        return payload

    remote_check = run_command(
        ssh_command(target, "$ErrorActionPreference = 'Stop'; wsl.exe -d Ubuntu -- bash -lc 'whoami && uname -m'")
    )
    payload["remote_check"] = remote_check
    payload["ok"] = remote_check["ok"]
    return payload


def execute(operation_id: str, approved: bool) -> dict[str, Any]:
    details = OPERATIONS.get(operation_id)
    if details is None:
        raise RuntimeError(f"Unknown operation: {operation_id}")
    if details["approval_required"] and not approved:
        raise PermissionError(f"{operation_id} requires --approve after explicit operator approval.")
    command = details.get("command") or wsl_bash_script_command(details["wsl_script"], details.get("wsl_user"))
    result = run_command(ssh_command(configured_target(), command))
    return {
        "tool_id": TOOL_ID,
        "operation": operation_id,
        "approval_required": details["approval_required"],
        "approved": approved,
        "result": result,
    }


def verify(operation_id: str) -> dict[str, Any]:
    verification_operation = "docker_status" if operation_id == "docker_install" else operation_id
    payload = execute(verification_operation, approved=False)
    payload["verified_operation"] = operation_id
    return payload


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description="Governed SSH/WSL adapter for the T480 AI Lab.")
    command_parser.add_argument("command", choices=["describe-requirements", "preflight", "execute", "verify"])
    command_parser.add_argument("--operation", choices=sorted(OPERATIONS), help="Fixed operation identifier.")
    command_parser.add_argument("--approve", action="store_true", help="Record explicit approval for a mutating operation.")
    return command_parser


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    validate_contract()
    if args.command == "describe-requirements":
        payload = requirements()
    elif args.command == "preflight":
        payload = preflight()
    else:
        if not args.operation:
            raise SystemExit("--operation is required for execute and verify")
        payload = execute(args.operation, args.approve) if args.command == "execute" else verify(args.operation)
    append_execution_log(args.command, args.operation, payload)
    print(json.dumps(payload, indent=2))
    if args.command == "describe-requirements":
        return 0
    return 0 if payload.get("ok", payload.get("result", {}).get("ok", False)) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PermissionError, RuntimeError) as error:
        print(json.dumps({"tool_id": TOOL_ID, "ok": False, "error": str(error)}, indent=2), file=sys.stderr)
        raise SystemExit(2)
