#!/usr/bin/env python3
"""Create and verify non-secret manifests for PostgreSQL logical backups."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "cs-ai-lab.backup-manifest.v1"
POSTGRES_LOGICAL_SCOPE = "postgres-logical"
FULL_LAB_SCOPE = "full-lab"
FULL_LAB_REQUIRED_ARTIFACTS = {
    "postgres_logical_dump",
    "compose_revision",
    "environment_recovery_record",
    "n8n_encryption_key_recovery_record",
    "n8n_data_recovery_record",
    "n8n_files_recovery_record",
}
RECOVERY_RECORD_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,127}\Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_postgres_manifest(
    *, dump_path: Path, source_revision: str, compose_path: Path, captured_at: str | None = None
) -> dict[str, Any]:
    if not dump_path.is_file() or dump_path.stat().st_size == 0:
        raise ValueError("PostgreSQL dump must be a non-empty file.")
    if not compose_path.is_file():
        raise ValueError("Compose file is required for the backup manifest.")
    if not source_revision or any(character.isspace() for character in source_revision):
        raise ValueError("Source revision must be a non-empty, whitespace-free identifier.")
    return {
        "schema_version": SCHEMA_VERSION,
        "captured_at": captured_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "source_revision": source_revision,
        "recovery_scope": POSTGRES_LOGICAL_SCOPE,
        "artifacts": [
            {
                "id": "postgres_logical_dump",
                "file": dump_path.name,
                "sha256": sha256_file(dump_path),
                "bytes": dump_path.stat().st_size,
            },
            {"id": "compose_revision", "sha256": sha256_file(compose_path)},
        ],
        "excluded_from_scope": sorted(FULL_LAB_REQUIRED_ARTIFACTS - {"postgres_logical_dump", "compose_revision"}),
    }


def _file_artifact(identifier: str, path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"{identifier} must be a non-empty file.")
    return {"id": identifier, "file": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size}


def _recovery_record(identifier: str, record_id: str) -> dict[str, str]:
    if not RECOVERY_RECORD_ID.fullmatch(record_id):
        raise ValueError(f"{identifier} must be an opaque identifier of 3-128 letters, digits, dots, underscores, or hyphens.")
    return {"id": identifier, "recovery_record_id": record_id}


def build_full_lab_manifest(
    *,
    dump_path: Path,
    n8n_data_archive: Path,
    n8n_files_archive: Path,
    source_revision: str,
    compose_path: Path,
    environment_recovery_record_id: str,
    n8n_encryption_key_recovery_record_id: str,
    captured_at: str | None = None,
) -> dict[str, Any]:
    """Build a full-lab manifest without ever including secret material."""
    base = build_postgres_manifest(dump_path=dump_path, source_revision=source_revision, compose_path=compose_path, captured_at=captured_at)
    return {
        **base,
        "recovery_scope": FULL_LAB_SCOPE,
        "artifacts": [
            _file_artifact("postgres_logical_dump", dump_path),
            {"id": "compose_revision", "sha256": sha256_file(compose_path)},
            _file_artifact("n8n_data_recovery_record", n8n_data_archive),
            _file_artifact("n8n_files_recovery_record", n8n_files_archive),
            _recovery_record("environment_recovery_record", environment_recovery_record_id),
            _recovery_record("n8n_encryption_key_recovery_record", n8n_encryption_key_recovery_record_id),
        ],
        "excluded_from_scope": [],
    }


def artifact_ids(manifest: dict[str, Any]) -> set[str]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("Manifest artifacts must be a list.")
    ids: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("id"), str):
            raise ValueError("Every manifest artifact needs a string id.")
        if artifact["id"] in ids:
            raise ValueError(f"Manifest contains duplicate artifact id: {artifact['id']}")
        ids.add(artifact["id"])
    return ids


def verify_manifest(manifest_path: Path, *, require_full_lab: bool = False) -> dict[str, Any]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read backup manifest: {error}") from error
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported or invalid backup manifest schema.")
    if not isinstance(manifest.get("captured_at"), str) or not isinstance(manifest.get("source_revision"), str):
        raise ValueError("Manifest is missing capture time or source revision.")
    ids = artifact_ids(manifest)
    artifacts_by_id = {artifact["id"]: artifact for artifact in manifest["artifacts"]}
    dump = artifacts_by_id.get("postgres_logical_dump")
    if not isinstance(dump, dict) or not isinstance(dump.get("file"), str) or not isinstance(dump.get("sha256"), str):
        raise ValueError("Manifest has no verifiable PostgreSQL logical dump.")
    for identifier, artifact in artifacts_by_id.items():
        if "file" not in artifact:
            continue
        filename = artifact.get("file")
        digest = artifact.get("sha256")
        if not isinstance(filename, str) or Path(filename).name != filename or not isinstance(digest, str):
            raise ValueError(f"Artifact {identifier} has an invalid file or SHA-256 field.")
        artifact_path = manifest_path.parent / filename
        if not artifact_path.is_file() or sha256_file(artifact_path) != digest:
            raise ValueError(f"Artifact {identifier} is absent or its SHA-256 does not match the manifest.")
    if require_full_lab:
        missing = sorted(FULL_LAB_REQUIRED_ARTIFACTS - ids)
        if missing:
            raise ValueError("Full-lab recovery preflight is incomplete; missing artifacts: " + ", ".join(missing))
        if manifest.get("recovery_scope") != FULL_LAB_SCOPE:
            raise ValueError("Full-lab recovery preflight requires a manifest whose recovery_scope is full-lab.")
        for identifier in {"postgres_logical_dump", "n8n_data_recovery_record", "n8n_files_recovery_record"}:
            if not isinstance(artifacts_by_id[identifier].get("file"), str):
                raise ValueError(f"Full-lab recovery preflight requires an archived file for {identifier}.")
        for identifier in {"environment_recovery_record", "n8n_encryption_key_recovery_record"}:
            value = artifacts_by_id[identifier].get("recovery_record_id")
            if not isinstance(value, str) or not RECOVERY_RECORD_ID.fullmatch(value):
                raise ValueError(f"Full-lab recovery preflight requires an opaque recovery record identifier for {identifier}.")
    return {"manifest": str(manifest_path), "scope": manifest.get("recovery_scope"), "artifact_ids": sorted(ids)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-postgres-logical")
    create.add_argument("--dump", required=True, type=Path)
    create.add_argument("--compose", required=True, type=Path)
    create.add_argument("--source-revision", required=True)
    create.add_argument("--output", required=True, type=Path)
    full = commands.add_parser("create-full-lab")
    full.add_argument("--dump", required=True, type=Path)
    full.add_argument("--n8n-data-archive", required=True, type=Path)
    full.add_argument("--n8n-files-archive", required=True, type=Path)
    full.add_argument("--compose", required=True, type=Path)
    full.add_argument("--source-revision", required=True)
    full.add_argument("--environment-recovery-record-id", required=True)
    full.add_argument("--n8n-encryption-key-recovery-record-id", required=True)
    full.add_argument("--output", required=True, type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("manifest", type=Path)
    verify.add_argument("--require-full-lab", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "create-postgres-logical":
            value = build_postgres_manifest(dump_path=args.dump, source_revision=args.source_revision, compose_path=args.compose)
            args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"Backup manifest created: {args.output}")
        elif args.command == "create-full-lab":
            value = build_full_lab_manifest(
                dump_path=args.dump,
                n8n_data_archive=args.n8n_data_archive,
                n8n_files_archive=args.n8n_files_archive,
                source_revision=args.source_revision,
                compose_path=args.compose,
                environment_recovery_record_id=args.environment_recovery_record_id,
                n8n_encryption_key_recovery_record_id=args.n8n_encryption_key_recovery_record_id,
            )
            args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"Full-lab backup manifest created: {args.output}")
        else:
            value = verify_manifest(args.manifest, require_full_lab=args.require_full_lab)
            print(json.dumps(value, sort_keys=True))
    except ValueError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
