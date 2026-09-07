#!/usr/bin/env python3
"""Pull one verified PostgreSQL backup bundle from the T480 to the T16.

Run only on the T16 after explicit approval. This tool never copies `.env`, an
n8n encryption key, raw evidence, or arbitrary remote paths. It transfers the
named logical dump and its non-secret manifest through the configured,
strict-host-key SSH target, then verifies the copied dump before retaining it.
"""

from __future__ import annotations

import argparse
import base64
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.backup_manifest import verify_manifest
    from scripts.t480_adapter import (
        configured_target,
        local_path_from_windows_folder,
        powershell_quote,
        run_command,
        windows_path,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from backup_manifest import verify_manifest
    from t480_adapter import configured_target, local_path_from_windows_folder, powershell_quote, run_command, windows_path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG_PATH = ROOT / ".t16-backup.local"
TARGET_MARKER = ".cs-ai-lab-t16-backup-target"
TARGET_MARKER_VALUE = "cs-ai-lab-t16-backup-target-v1\n"
REMOTE_BACKUP_DIRECTORY = "/home/chris/projects/cs-ai-lab-infra/postgres/backup"
BACKUP_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*-[0-9]{8}T[0-9]{6}[+-][0-9]{4}\.sql\.gz\Z")
FULL_LAB_BUNDLE_ID = re.compile(r"w1-[0-9]{8}T[0-9]{6}Z\Z")


def read_local_config(environ: dict[str, str] | None = None) -> dict[str, str]:
    # Tests and callers that provide an explicit environment get exactly that
    # configuration. They must not silently inherit an encryption assertion
    # from an unrelated local target file.
    values = dict(os.environ if environ is None else environ)
    if environ is None and LOCAL_CONFIG_PATH.is_file():
        for raw in LOCAL_CONFIG_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            if separator and key in {"T16_BACKUP_ROOT", "T16_BACKUP_ENCRYPTION_CONFIRMED"}:
                values.setdefault(key, value.strip())
    return values


def backup_target(environ: dict[str, str] | None = None) -> Path:
    values = read_local_config(environ)
    value = values.get("T16_BACKUP_ROOT", "")
    if not value:
        raise RuntimeError(
            "Missing T16_BACKUP_ROOT. Copy t16/backup-target.local.example to .t16-backup.local on the T16."
        )
    if values.get("T16_BACKUP_ENCRYPTION_CONFIRMED") != "yes":
        raise RuntimeError("Refusing transfer until T16_BACKUP_ENCRYPTION_CONFIRMED=yes records the encrypted-volume preflight.")
    target = local_path_from_windows_folder(value).resolve()
    if target == ROOT or ROOT in target.parents:
        raise RuntimeError("T16 backup target must be outside the repository worktree.")
    return target


def configure_target(target_dir: str, *, encryption_confirmed: bool) -> Path:
    """Write the ignored local target config only after an explicit preflight assertion."""
    if not encryption_confirmed:
        raise RuntimeError("Refusing to configure a target until its encrypted volume has been confirmed.")
    target = local_path_from_windows_folder(target_dir).resolve()
    if target == ROOT or ROOT in target.parents:
        raise RuntimeError("T16 backup target must be outside the repository worktree.")
    if LOCAL_CONFIG_PATH.exists():
        raise RuntimeError("A .t16-backup.local configuration already exists; review it rather than overwriting it.")
    temporary = LOCAL_CONFIG_PATH.with_suffix(".local.tmp")
    temporary.write_text(
        f"T16_BACKUP_ROOT={target_dir}\nT16_BACKUP_ENCRYPTION_CONFIRMED=yes\n", encoding="utf-8"
    )
    temporary.chmod(0o600)
    temporary.replace(LOCAL_CONFIG_PATH)
    return target


def validate_backup_name(value: str) -> str:
    if not BACKUP_NAME.fullmatch(value):
        raise ValueError("Backup name must be a timestamped .sql.gz basename produced by scripts/backup.sh.")
    return value


def manifest_name(backup_name: str) -> str:
    validate_backup_name(backup_name)
    return backup_name.removesuffix(".sql.gz") + ".manifest.json"


def validate_full_lab_bundle_id(value: str) -> str:
    if not FULL_LAB_BUNDLE_ID.fullmatch(value):
        raise ValueError("Full-lab bundle ID must be a w1-YYYYMMDDThhmmssZ basename.")
    return value


def prepare_target(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    marker = target / TARGET_MARKER
    if marker.exists() and marker.read_text(encoding="utf-8") != TARGET_MARKER_VALUE:
        raise RuntimeError("Refusing target with an unrecognised CS AI Lab backup marker.")
    if not marker.exists():
        marker.write_text(TARGET_MARKER_VALUE, encoding="utf-8")


def require_prepared_target(target: Path) -> None:
    marker = target / TARGET_MARKER
    if not marker.is_file() or marker.read_text(encoding="utf-8") != TARGET_MARKER_VALUE:
        raise RuntimeError("T16 target is not prepared. Run prepare-target with --approve after verifying encryption and capacity.")


def powershell_scp(remote_files: list[str], destination: Path) -> dict[str, Any]:
    destination_windows = windows_path(destination)
    sources = " ".join(powershell_quote(f"{configured_target()}:{REMOTE_BACKUP_DIRECTORY}/{name}") for name in remote_files)
    command = (
        "$ErrorActionPreference = 'Stop'; "
        f"& scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- {sources} {powershell_quote(destination_windows)}; "
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    )
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    return run_command(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded])


def powershell_scp_full_lab(bundle_id: str, destination: Path) -> dict[str, Any]:
    bundle_id = validate_full_lab_bundle_id(bundle_id)
    destination_windows = windows_path(destination)
    source = powershell_quote(f"{configured_target()}:{REMOTE_BACKUP_DIRECTORY}/full-lab/{bundle_id}")
    command = (
        "$ErrorActionPreference = 'Stop'; "
        f"& scp.exe -r -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- {source} {powershell_quote(destination_windows)}; "
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    )
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    return run_command(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded])


def pull(backup_name: str, target: Path) -> dict[str, Any]:
    backup_name = validate_backup_name(backup_name)
    require_prepared_target(target)
    manifest = manifest_name(backup_name)
    final_dump = target / backup_name
    final_manifest = target / manifest
    if final_dump.exists() or final_manifest.exists():
        raise RuntimeError("Refusing to overwrite an existing retained T16 backup bundle.")
    staging = target / f".incoming-{backup_name}"
    staging.mkdir()
    try:
        transfer = powershell_scp([backup_name, manifest], staging)
        if not transfer.get("ok"):
            return {"backup": backup_name, "transfer": transfer, "ok": False}
        copied_manifest = staging / manifest
        verification = verify_manifest(copied_manifest)
        shutil.move(str(staging / backup_name), final_dump)
        shutil.move(str(copied_manifest), final_manifest)
        return {
            "backup": backup_name,
            "manifest_sha256": __import__("hashlib").sha256(final_manifest.read_bytes()).hexdigest(),
            "scope": verification["scope"],
            "ok": True,
        }
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def pull_full_lab(bundle_id: str, target: Path) -> dict[str, Any]:
    bundle_id = validate_full_lab_bundle_id(bundle_id)
    require_prepared_target(target)
    final_bundle = target / bundle_id
    if final_bundle.exists():
        raise RuntimeError("Refusing to overwrite an existing retained T16 full-lab bundle.")
    staging = target / f".incoming-{bundle_id}"
    staging.mkdir()
    try:
        transfer = powershell_scp_full_lab(bundle_id, staging)
        if not transfer.get("ok"):
            return {"bundle_id": bundle_id, "transfer": transfer, "ok": False}
        copied_bundle = staging / bundle_id
        verification = verify_manifest(copied_bundle / "manifest.json", require_full_lab=True)
        shutil.move(str(copied_bundle), final_bundle)
        return {
            "bundle_id": bundle_id,
            "manifest_sha256": __import__("hashlib").sha256((final_bundle / "manifest.json").read_bytes()).hexdigest(),
            "scope": verification["scope"],
            "ok": True,
        }
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description=__doc__)
    command_parser.add_argument("command", choices=["prepare-target", "pull", "pull-full-lab"])
    command_parser.add_argument("--backup-name")
    command_parser.add_argument("--bundle-id")
    command_parser.add_argument("--target-dir", help="Dedicated encrypted T16 volume path; used only when first preparing the target.")
    command_parser.add_argument("--confirm-encrypted-volume", action="store_true")
    command_parser.add_argument("--approve", action="store_true")
    return command_parser


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.approve:
        raise PermissionError(f"{args.command} requires --approve after explicit operator approval.")
    if args.command == "prepare-target":
        if args.target_dir:
            configure_target(args.target_dir, encryption_confirmed=args.confirm_encrypted_volume)
        elif args.confirm_encrypted_volume:
            raise SystemExit("--confirm-encrypted-volume requires --target-dir when preparing a new target.")
        target = backup_target()
        prepare_target(target)
        print("T16 backup target prepared; encryption status was supplied by local preflight.")
        return 0
    if args.target_dir or args.confirm_encrypted_volume:
        raise SystemExit("--target-dir and --confirm-encrypted-volume are only valid for prepare-target.")
    if args.command == "pull-full-lab":
        if not args.bundle_id:
            raise SystemExit("pull-full-lab requires --bundle-id")
        target = backup_target()
        result = pull_full_lab(args.bundle_id, target)
    elif not args.backup_name:
        raise SystemExit("pull requires --backup-name")
    else:
        target = backup_target()
        result = pull(args.backup_name, target)
    print({key: value for key, value in result.items() if key != "transfer"})
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PermissionError, RuntimeError, ValueError) as error:
        print(f"T16 backup pull refused: {error}", file=sys.stderr)
        raise SystemExit(2)
