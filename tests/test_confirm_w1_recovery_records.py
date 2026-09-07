import importlib.util
from pathlib import Path
from unittest import mock

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("confirm_w1_recovery_records", ROOT / "scripts/confirm-w1-recovery-records.py")
assert SPEC and SPEC.loader
confirm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(confirm)


def test_confirmation_requires_configured_opaque_record_ids(tmp_path: Path):
    path = tmp_path / ".w1-recovery.local"
    with mock.patch.object(confirm, "CONFIG_PATH", path):
        with pytest.raises(RuntimeError, match="missing"):
            confirm.confirm()
        path.write_text("W1_RECOVERY_RECORDS_CONFIRMED=no\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="missing recovery record IDs"):
            confirm.confirm()


def test_confirmation_flips_only_the_local_confirmation_gate(tmp_path: Path):
    path = tmp_path / ".w1-recovery.local"
    path.write_text(
        "W1_ENVIRONMENT_RECOVERY_RECORD_ID=owner-env-record\n"
        "W1_N8N_ENCRYPTION_KEY_RECOVERY_RECORD_ID=owner-n8n-key-record\n"
        "W1_RECOVERY_RECORDS_CONFIRMED=no\n"
        "W1_RPO_HOURS=24\n",
        encoding="utf-8",
    )
    with mock.patch.object(confirm, "CONFIG_PATH", path):
        confirm.confirm()
    rendered = path.read_text(encoding="utf-8")
    assert "W1_RECOVERY_RECORDS_CONFIRMED=yes" in rendered
    assert "W1_RPO_HOURS=24" in rendered
