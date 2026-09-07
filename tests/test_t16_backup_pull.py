import json
from pathlib import Path
from unittest import mock

import pytest

from scripts import t16_backup_pull
from scripts.backup_manifest import build_full_lab_manifest, build_postgres_manifest


def test_target_requires_encryption_confirmation_and_stays_outside_repo(tmp_path: Path):
    with pytest.raises(RuntimeError, match="ENCRYPTION_CONFIRMED"):
        t16_backup_pull.backup_target({"T16_BACKUP_ROOT": str(tmp_path)})
    with pytest.raises(RuntimeError, match="outside the repository"):
        t16_backup_pull.backup_target({"T16_BACKUP_ROOT": str(t16_backup_pull.ROOT), "T16_BACKUP_ENCRYPTION_CONFIRMED": "yes"})


def test_backup_names_are_fixed_and_manifest_name_is_derived():
    name = "cs_ai_lab-20260907T120000+1200.sql.gz"
    assert t16_backup_pull.manifest_name(name) == "cs_ai_lab-20260907T120000+1200.manifest.json"
    with pytest.raises(ValueError):
        t16_backup_pull.validate_backup_name("../../.env")
    assert t16_backup_pull.validate_full_lab_bundle_id("w1-20260907T120000Z") == "w1-20260907T120000Z"
    with pytest.raises(ValueError):
        t16_backup_pull.validate_full_lab_bundle_id("../../.env")


def test_prepared_target_requires_the_exact_marker(tmp_path: Path):
    t16_backup_pull.prepare_target(tmp_path)
    t16_backup_pull.require_prepared_target(tmp_path)
    (tmp_path / t16_backup_pull.TARGET_MARKER).write_text("wrong\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="unrecognised"):
        t16_backup_pull.prepare_target(tmp_path)


def test_configure_target_writes_ignored_local_config_only_after_confirmation(tmp_path: Path):
    config = tmp_path / ".t16-backup.local"
    target = tmp_path / "encrypted-target"
    with mock.patch.object(t16_backup_pull, "LOCAL_CONFIG_PATH", config):
        with pytest.raises(RuntimeError, match="encrypted volume"):
            t16_backup_pull.configure_target(str(target), encryption_confirmed=False)
        result = t16_backup_pull.configure_target(str(target), encryption_confirmed=True)
        assert result == target.resolve()
        assert "T16_BACKUP_ROOT=" in config.read_text(encoding="utf-8")
        assert "T16_BACKUP_ENCRYPTION_CONFIRMED=yes" in config.read_text(encoding="utf-8")
        with pytest.raises(RuntimeError, match="already exists"):
            t16_backup_pull.configure_target(str(target), encryption_confirmed=True)


def test_pull_verifies_before_retaining_and_never_overwrites(tmp_path: Path):
    target = tmp_path / "target"
    t16_backup_pull.prepare_target(target)
    backup = "cs_ai_lab-20260907T120000+1200.sql.gz"
    manifest_name = t16_backup_pull.manifest_name(backup)

    def fake_scp(_files, destination):
        dump = destination / backup
        dump.write_bytes(b"synthetic dump")
        compose = destination / "compose.yaml"
        compose.write_text("services: {}\n", encoding="utf-8")
        manifest = build_postgres_manifest(dump_path=dump, compose_path=compose, source_revision="a" * 40)
        (destination / manifest_name).write_text(json.dumps(manifest), encoding="utf-8")
        return {"ok": True}

    with mock.patch.object(t16_backup_pull, "powershell_scp", side_effect=fake_scp):
        result = t16_backup_pull.pull(backup, target)
    assert result["ok"] is True
    assert (target / backup).is_file()
    assert (target / manifest_name).is_file()
    with pytest.raises(RuntimeError, match="overwrite"):
        t16_backup_pull.pull(backup, target)


def test_pull_discards_unverified_staging_bundle(tmp_path: Path):
    target = tmp_path / "target"
    t16_backup_pull.prepare_target(target)
    backup = "cs_ai_lab-20260907T120000+1200.sql.gz"

    def fake_scp(_files, destination):
        (destination / backup).write_bytes(b"tampered")
        (destination / t16_backup_pull.manifest_name(backup)).write_text("{}", encoding="utf-8")
        return {"ok": True}

    with mock.patch.object(t16_backup_pull, "powershell_scp", side_effect=fake_scp), pytest.raises(ValueError):
        t16_backup_pull.pull(backup, target)
    assert not list(target.glob(".incoming-*"))
    assert not (target / backup).exists()


def test_full_lab_pull_verifies_bundle_before_retaining(tmp_path: Path):
    target = tmp_path / "target"
    t16_backup_pull.prepare_target(target)
    bundle_id = "w1-20260907T120000Z"

    def fake_scp(_bundle_id, destination):
        bundle = destination / bundle_id
        bundle.mkdir()
        dump, data, files = bundle / "postgres.sql.gz", bundle / "n8n-data.tar.gz", bundle / "n8n-files.tar.gz"
        for path in (dump, data, files):
            path.write_bytes(b"synthetic")
        compose = bundle / "compose.yaml"
        compose.write_text("services: {}\n", encoding="utf-8")
        manifest = build_full_lab_manifest(
            dump_path=dump, n8n_data_archive=data, n8n_files_archive=files, compose_path=compose, source_revision="d" * 40,
            environment_recovery_record_id="env-record", n8n_encryption_key_recovery_record_id="key-record",
        )
        (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return {"ok": True}

    with mock.patch.object(t16_backup_pull, "stage_full_lab_for_windows_scp", return_value={"ok": True}), mock.patch.object(
        t16_backup_pull, "cleanup_windows_scp_staging", return_value={"ok": True}
    ), mock.patch.object(t16_backup_pull, "powershell_scp_full_lab", side_effect=fake_scp):
        result = t16_backup_pull.pull_full_lab(bundle_id, target)
    assert result["ok"] is True
    assert (target / bundle_id / "manifest.json").is_file()


def test_failed_transfer_keeps_incoming_bytes_and_source_for_resume(tmp_path):
    target = tmp_path / 'target'
    t16_backup_pull.prepare_target(target)
    identifier = 'w1-20260907T120000Z'
    def interrupted(_identifier, destination):
        bundle = destination / identifier
        bundle.mkdir(exist_ok=True)
        (bundle / 'postgres.sql.gz').write_bytes(b'partial')
        return {'ok': False, 'exit_code': 255}
    with mock.patch.object(t16_backup_pull, 'stage_full_lab_for_windows_scp', return_value={'ok': True}), mock.patch.object(
        t16_backup_pull, 'powershell_scp_full_lab', side_effect=interrupted
    ), mock.patch.object(t16_backup_pull, 'cleanup_windows_scp_staging') as cleanup:
        result = t16_backup_pull.pull_full_lab(identifier, target)
    assert not result['ok']
    assert not (target / identifier).exists()
    assert (target / ('.incoming-' + identifier) / identifier / 'postgres.sql.gz').read_bytes() == b'partial'
    assert not (target / ('.incoming-' + identifier) / '.transfer.lock').exists()
    cleanup.assert_not_called()


def test_sftp_resumes_fixed_artifacts_and_refreshes_manifest(tmp_path):
    identifier = 'w1-20260907T120000Z'
    captured = []
    def run(_command):
        captured.append((tmp_path / 'transfer.sftp').read_text())
        return {'ok': True}
    with mock.patch.object(t16_backup_pull, 'run_command', side_effect=run), mock.patch.object(
        t16_backup_pull, 'windows_path', side_effect=lambda p: 'C:/backup/' + p.name
    ), mock.patch.object(t16_backup_pull, 'configured_target', return_value='configured-target'):
        assert t16_backup_pull.powershell_scp_full_lab(identifier, tmp_path)['ok']
    assert captured[0].splitlines()[0].startswith('get ')
    assert len([line for line in captured[0].splitlines() if line.startswith('reget ')]) == 3
    assert not (tmp_path / 'transfer.sftp').exists()


def test_full_lab_hash_mismatch_never_retains_or_deletes_source(tmp_path):
    target = tmp_path / 'target'
    t16_backup_pull.prepare_target(target)
    identifier = 'w1-20260907T120000Z'
    def corrupt(_identifier, destination):
        bundle = destination / identifier
        bundle.mkdir(exist_ok=True)
        (bundle / 'manifest.json').write_text('{}')
        return {'ok': True}
    with mock.patch.object(t16_backup_pull, 'stage_full_lab_for_windows_scp', return_value={'ok': True}), mock.patch.object(
        t16_backup_pull, 'powershell_scp_full_lab', side_effect=corrupt
    ), mock.patch.object(t16_backup_pull, 'cleanup_windows_scp_staging') as cleanup, pytest.raises(ValueError):
        t16_backup_pull.pull_full_lab(identifier, target)
    assert not (target / identifier).exists()
    cleanup.assert_not_called()


def test_full_lab_existing_lock_refuses_second_transfer(tmp_path):
    target = tmp_path / 'target'
    t16_backup_pull.prepare_target(target)
    identifier = 'w1-20260907T120000Z'
    staging = target / ('.incoming-' + identifier)
    staging.mkdir()
    (staging / '.transfer.lock').touch()
    with mock.patch.object(t16_backup_pull, 'stage_full_lab_for_windows_scp') as remote, pytest.raises(RuntimeError, match='lock'):
        t16_backup_pull.pull_full_lab(identifier, target)
    remote.assert_not_called()
