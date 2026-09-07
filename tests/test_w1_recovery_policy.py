import importlib.util
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("configure_w1_recovery_policy", ROOT / "scripts/configure-w1-recovery-policy.py")
assert SPEC and SPEC.loader
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


def test_policy_writes_nonsecret_defaults_and_requires_explicit_record_confirmation(tmp_path: Path):
    config = tmp_path / ".w1-recovery.local"
    with mock.patch.object(policy, "CONFIG_PATH", config):
        policy.configure(
            environment_record_id="owner-password-manager-env-v1",
            key_record_id="owner-password-manager-key-v1",
            rpo_hours=24,
            rto_hours=4,
            retention_daily=30,
            confirm_records=False,
        )
    rendered = config.read_text(encoding="utf-8")
    assert "W1_RECOVERY_RECORDS_CONFIRMED=no" in rendered
    assert "W1_OLLAMA_MODEL_DISPOSITION=redownload-reviewed-models" in rendered
    assert "N8N_ENCRYPTION_KEY=" not in rendered


def test_policy_rejects_bad_values_and_overwrite(tmp_path: Path):
    config = tmp_path / ".w1-recovery.local"
    with mock.patch.object(policy, "CONFIG_PATH", config):
        with pytest.raises(ValueError, match="positive"):
            policy.configure(
                environment_record_id="env-record", key_record_id="key-record", rpo_hours=0, rto_hours=4, retention_daily=30,
                confirm_records=False,
            )
        policy.configure(
            environment_record_id="env-record", key_record_id="key-record", rpo_hours=24, rto_hours=4, retention_daily=30,
            confirm_records=True,
        )
        with pytest.raises(RuntimeError, match="already exists"):
            policy.configure(
                environment_record_id="env-record", key_record_id="key-record", rpo_hours=24, rto_hours=4, retention_daily=30,
                confirm_records=True,
            )
