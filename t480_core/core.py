"""Governed PowerShell -> Windows OpenSSH -> WSL transport.

The public application CLIs must expose fixed operation identifiers only.
This module owns quoting, target resolution, timeouts, structured results,
catalog consistency checks, and metadata-only audit logging.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Iterable, Mapping, Sequence

_SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
_SAFE_TARGET = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@:-]*\Z")
_EXPECTED_SCHEMA = "cs-ai-lab.t480.transport.v1"
_CONFIG_FIELDS = {
    "schema_version",
    "ssh_target_env",
    "wsl_distribution",
    "connect_timeout_seconds",
    "command_timeout_seconds",
    "long_command_timeout_seconds",
    "strict_host_key_checking",
    "batch_mode",
}


@dataclass(frozen=True)
class TransportSettings:
    schema_version: str = _EXPECTED_SCHEMA
    ssh_target_env: str = "T480_SSH_TARGET"
    wsl_distribution: str = "Ubuntu"
    connect_timeout_seconds: int = 10
    command_timeout_seconds: int = 30
    long_command_timeout_seconds: int = 14_400
    strict_host_key_checking: bool = True
    batch_mode: bool = True

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "TransportSettings":
        unknown = set(values) - _CONFIG_FIELDS
        if unknown:
            raise ValueError(f"Unknown T480 transport configuration fields: {', '.join(sorted(unknown))}")
        settings = cls(**dict(values))
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.schema_version != _EXPECTED_SCHEMA:
            raise ValueError(f"schema_version must be {_EXPECTED_SCHEMA}")
        if not _SAFE_IDENTIFIER.fullmatch(self.ssh_target_env):
            raise ValueError("ssh_target_env must be a safe environment variable name")
        if not _SAFE_IDENTIFIER.fullmatch(self.wsl_distribution):
            raise ValueError("wsl_distribution must be a safe WSL distribution name")
        if not 1 <= self.connect_timeout_seconds <= 60:
            raise ValueError("connect_timeout_seconds must be between 1 and 60")
        if not 1 <= self.command_timeout_seconds <= 900:
            raise ValueError("command_timeout_seconds must be between 1 and 900")
        if not self.command_timeout_seconds <= self.long_command_timeout_seconds <= 86_400:
            raise ValueError("long_command_timeout_seconds must be between command timeout and 86400")
        if self.strict_host_key_checking is not True:
            raise ValueError("strict_host_key_checking cannot be disabled")
        if self.batch_mode is not True:
            raise ValueError("batch_mode cannot be disabled")


@dataclass(frozen=True)
class Operation:
    operation_id: str
    purpose: str
    approval_required: bool = False
    powershell_command: str | None = None
    wsl_script: str | None = None
    wsl_user: str | None = None
    timeout_seconds: int | None = None

    def validate(self) -> None:
        if not _SAFE_IDENTIFIER.fullmatch(self.operation_id):
            raise ValueError(f"Unsafe operation identifier: {self.operation_id!r}")
        if not self.purpose.strip():
            raise ValueError(f"Operation {self.operation_id} requires a purpose")
        if (self.powershell_command is None) == (self.wsl_script is None):
            raise ValueError(f"Operation {self.operation_id} must define exactly one execution surface")
        if self.wsl_user is not None and not _SAFE_IDENTIFIER.fullmatch(self.wsl_user):
            raise ValueError(f"Operation {self.operation_id} has an unsafe WSL user")
        if self.timeout_seconds is not None and not 1 <= self.timeout_seconds <= 86_400:
            raise ValueError(f"Operation {self.operation_id} has an invalid timeout")


def load_transport_settings(path: Path) -> TransportSettings:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError("T480 transport configuration must be a JSON object")
    return TransportSettings.from_mapping(payload)


def _read_env_file(path: Path, variable_name: str) -> str:
    if not path.is_file():
        return ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if separator and name.strip() == variable_name:
            return value.strip()
    return ""


def validate_ssh_target(target: str) -> str:
    value = target.strip()
    if not _SAFE_TARGET.fullmatch(value) or value.startswith("-"):
        raise ValueError("T480 SSH target must be a host alias or user@host without whitespace or options")
    return value


def resolve_ssh_target(settings: TransportSettings, config_paths: Iterable[Path]) -> str:
    target = os.environ.get(settings.ssh_target_env, "").strip()
    if not target:
        for path in config_paths:
            target = _read_env_file(path, settings.ssh_target_env)
            if target:
                break
    if not target:
        raise RuntimeError(
            f"Set {settings.ssh_target_env} or add it to an ignored machine-local T480 configuration file."
        )
    return validate_ssh_target(target)


def build_ssh_command(target: str, powershell_command: str, settings: TransportSettings) -> list[str]:
    safe_target = validate_ssh_target(target)
    encoded_command = base64.b64encode(powershell_command.encode("utf-16-le")).decode("ascii")
    encoded_target = base64.b64encode(safe_target.encode()).decode("ascii")
    return [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "$target=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"
            + encoded_target
            + "')); "
            "$remoteCommand='powershell.exe -NoProfile -NonInteractive -EncodedCommand "
            + encoded_command
            + "'; "
            "$sshArguments=@('-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout="
            + str(settings.connect_timeout_seconds)
            + "',$target,$remoteCommand); & ssh.exe @sshArguments"
        ),
    ]


def build_wsl_powershell_command(
    script: str,
    settings: TransportSettings,
    user: str | None = None,
) -> str:
    encoded_script = base64.b64encode(script.encode()).decode("ascii")
    distribution = settings.wsl_distribution
    if user is not None and not _SAFE_IDENTIFIER.fullmatch(user):
        raise ValueError("WSL user must be a safe identifier")
    user_argument = f" -u {user}" if user else ""
    return (
        "$ErrorActionPreference='Stop'; '"
        + encoded_script
        + "' | wsl.exe -d "
        + distribution
        + user_argument
        + " -- bash -c 'base64 -d | bash'"
    )


def run_command(command: Sequence[str], timeout_seconds: int) -> dict[str, Any]:
    started_at = datetime.now(UTC).isoformat(timespec="seconds")
    started = time.monotonic()
    try:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
        exit_code = completed.returncode
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
    except subprocess.TimeoutExpired as error:
        exit_code = 124
        stdout = (error.stdout or "").strip() if isinstance(error.stdout, str) else ""
        stderr = f"T480 operation exceeded {timeout_seconds} seconds"
    except OSError as error:
        exit_code = 127
        stdout = ""
        stderr = str(error)
    return {
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "duration_ms": round((time.monotonic() - started) * 1000),
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "ok": exit_code == 0,
    }


def execute_operation(
    operation: Operation,
    *,
    target: str,
    settings: TransportSettings,
    approved: bool = False,
) -> dict[str, Any]:
    operation.validate()
    if operation.approval_required and not approved:
        raise PermissionError(f"{operation.operation_id} requires explicit operator approval")
    powershell_command = operation.powershell_command or build_wsl_powershell_command(
        operation.wsl_script or "",
        settings,
        operation.wsl_user,
    )
    result = run_command(
        build_ssh_command(target, powershell_command, settings),
        timeout_seconds=operation.timeout_seconds or settings.command_timeout_seconds,
    )
    return {
        "operation": operation.operation_id,
        "approval_required": operation.approval_required,
        "approved": approved,
        "result": result,
        "ok": result["ok"],
    }


def preflight(
    *,
    tool_id: str,
    settings: TransportSettings,
    config_paths: Iterable[Path],
) -> dict[str, Any]:
    checks = {
        "powershell_available": shutil.which("powershell.exe") is not None,
        "windows_ssh_available": shutil.which("ssh.exe") is not None,
        "strict_host_key_checking": settings.strict_host_key_checking,
        "batch_mode": settings.batch_mode,
        "ssh_target_configured": False,
    }
    try:
        target = resolve_ssh_target(settings, config_paths)
        checks["ssh_target_configured"] = True
    except (RuntimeError, ValueError) as error:
        return {"tool_id": tool_id, "local_checks": checks, "ok": False, "error": str(error)}
    payload: dict[str, Any] = {"tool_id": tool_id, "local_checks": checks}
    if not all(checks.values()):
        payload["ok"] = False
        return payload
    command = build_ssh_command(
        target,
        build_wsl_powershell_command("set -euo pipefail\nwhoami\nuname -m\n", settings),
        settings,
    )
    payload["remote_check"] = run_command(command, settings.command_timeout_seconds)
    payload["ok"] = payload["remote_check"]["ok"]
    return payload


def validate_catalog(catalog_path: Path, operations: Mapping[str, Operation]) -> None:
    with catalog_path.open(encoding="utf-8") as file:
        catalog = json.load(file)
    if not isinstance(catalog, dict) or not isinstance(catalog.get("operations"), list):
        raise ValueError("T480 command catalog must contain an operations array")
    catalog_entries = catalog["operations"]
    catalog_ids = [str(entry.get("id", "")) for entry in catalog_entries if isinstance(entry, dict)]
    if len(catalog_ids) != len(set(catalog_ids)):
        raise ValueError("T480 command catalog contains duplicate operation IDs")
    if set(catalog_ids) != set(operations):
        raise ValueError("Adapter and command catalog operation IDs differ")
    for operation_id, operation in operations.items():
        operation.validate()
        entry = next(item for item in catalog_entries if item["id"] == operation_id)
        if bool(entry.get("approval_required", False)) != operation.approval_required:
            raise ValueError(f"Catalog approval policy differs for {operation_id}")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def fingerprint_files(paths: Iterable[Path]) -> str:
    """Hash ordered configuration contents without embedding machine paths."""
    digest = hashlib.sha256()
    for index, path in enumerate(paths):
        content = path.read_bytes()
        digest.update(str(index).encode())
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def append_execution_log(
    path: Path,
    *,
    tool_id: str,
    command_name: str,
    operation_id: str | None,
    payload: Mapping[str, Any],
) -> None:
    """Append metadata and hashes without retaining remote stdout or stderr."""
    result = payload.get("result") or payload.get("remote_check") or {}
    if not isinstance(result, Mapping):
        result = {}
    stdout = str(result.get("stdout", ""))
    stderr = str(result.get("stderr", ""))
    entry = {
        "logged_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool_id": tool_id,
        "command": command_name,
        "operation": operation_id,
        "approval_required": payload.get("approval_required"),
        "approved": payload.get("approved"),
        "configuration_fingerprint": payload.get("configuration_fingerprint"),
        "started_at": result.get("started_at"),
        "finished_at": result.get("finished_at"),
        "duration_ms": result.get("duration_ms"),
        "exit_code": result.get("exit_code"),
        "ok": payload.get("ok", result.get("ok")),
        "stdout_bytes": len(stdout.encode()),
        "stderr_bytes": len(stderr.encode()),
        "stdout_sha256": _digest(stdout),
        "stderr_sha256": _digest(stderr),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, separators=(",", ":")) + "\n")
