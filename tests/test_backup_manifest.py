import json
from pathlib import Path

import pytest

from scripts.backup_manifest import (
    FULL_LAB_REQUIRED_ARTIFACTS,
    POSTGRES_LOGICAL_SCOPE,
    build_postgres_manifest,
    build_full_lab_manifest,
    verify_manifest,
)


def create_manifest(tmp_path: Path) -> Path:
    dump = tmp_path / "lab.sql.gz"
    dump.write_bytes(b"synthetic logical dump")
    compose = tmp_path / "compose.yaml"
    compose.write_text("services: {}\n", encoding="utf-8")
    manifest = build_postgres_manifest(
        dump_path=dump, compose_path=compose, source_revision="a" * 40, captured_at="2026-09-07T00:00:00+00:00"
    )
    path = tmp_path / "lab.manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_postgres_logical_manifest_is_nonsecret_and_hash_verifiable(tmp_path: Path):
    path = create_manifest(tmp_path)
    value = verify_manifest(path)
    assert value["scope"] == POSTGRES_LOGICAL_SCOPE
    assert "postgres_logical_dump" in value["artifact_ids"]
    rendered = path.read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD" not in rendered
    assert "N8N_ENCRYPTION_KEY" not in rendered


def test_tampered_dump_fails_integrity_check(tmp_path: Path):
    path = create_manifest(tmp_path)
    (tmp_path / "lab.sql.gz").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        verify_manifest(path)


def test_full_lab_preflight_names_every_missing_required_artifact(tmp_path: Path):
    path = create_manifest(tmp_path)
    with pytest.raises(ValueError) as error:
        verify_manifest(path, require_full_lab=True)
    for artifact in FULL_LAB_REQUIRED_ARTIFACTS - {"postgres_logical_dump", "compose_revision"}:
        assert artifact in str(error.value)


def test_full_lab_manifest_requires_full_lab_scope_even_with_artifacts(tmp_path: Path):
    path = create_manifest(tmp_path)
    value = json.loads(path.read_text(encoding="utf-8"))
    value["artifacts"].extend({"id": artifact} for artifact in FULL_LAB_REQUIRED_ARTIFACTS - {"postgres_logical_dump", "compose_revision"})
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="recovery_scope"):
        verify_manifest(path, require_full_lab=True)


def test_full_lab_manifest_verifies_archives_and_opaque_secret_records(tmp_path: Path):
    dump = tmp_path / "postgres.sql.gz"
    data = tmp_path / "n8n-data.tar.gz"
    files = tmp_path / "n8n-files.tar.gz"
    compose = tmp_path / "compose.yaml"
    for path in (dump, data, files):
        path.write_bytes(path.name.encode("utf-8"))
    compose.write_text("services: {}\n", encoding="utf-8")
    manifest = build_full_lab_manifest(
        dump_path=dump,
        n8n_data_archive=data,
        n8n_files_archive=files,
        compose_path=compose,
        source_revision="b" * 40,
        environment_recovery_record_id="env-recovery-2026-09",
        n8n_encryption_key_recovery_record_id="n8n-key-recovery-2026-09",
    )
    path = tmp_path / "full.manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    value = verify_manifest(path, require_full_lab=True)
    assert value["scope"] == "full-lab"
    rendered = path.read_text(encoding="utf-8")
    assert "N8N_ENCRYPTION_KEY=" not in rendered


def test_full_lab_manifest_rejects_tampered_volume_archive(tmp_path: Path):
    dump = tmp_path / "postgres.sql.gz"
    data = tmp_path / "n8n-data.tar.gz"
    files = tmp_path / "n8n-files.tar.gz"
    compose = tmp_path / "compose.yaml"
    for path in (dump, data, files):
        path.write_bytes(b"synthetic")
    compose.write_text("services: {}\n", encoding="utf-8")
    manifest = build_full_lab_manifest(
        dump_path=dump, n8n_data_archive=data, n8n_files_archive=files, compose_path=compose, source_revision="c" * 40,
        environment_recovery_record_id="env-recovery", n8n_encryption_key_recovery_record_id="key-recovery",
    )
    path = tmp_path / "full.manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    data.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="n8n_data_recovery_record"):
        verify_manifest(path, require_full_lab=True)
