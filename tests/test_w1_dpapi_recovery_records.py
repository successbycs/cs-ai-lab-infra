import importlib.util
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("w1_dpapi_records", ROOT / "scripts/create-w1-dpapi-recovery-records.py")
assert SPEC and SPEC.loader
records = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(records)


def test_powershell_script_keeps_source_and_plaintext_out_of_output_contract():
    script = records.powershell_record_script("C:\\backup")
    assert "ConvertFrom-SecureString" in script
    assert "CurrentUser-DPAPI" in script
    assert "N8N_ENCRYPTION_KEY" in script
    assert "ConvertTo-Json" in script
    assert "[Console]::In.ReadToEnd()" in script
    assert "environmentText" not in script.split("ConvertTo-Json", 1)[1]
    assert "keyMatch.Groups[1].Value" not in script.split("ConvertTo-Json", 1)[1]


def test_mark_records_confirmed_replaces_prior_record_ids_only_after_record_creation(tmp_path: Path):
    policy = tmp_path / ".w1-recovery.local"
    policy.write_text(
        "W1_ENVIRONMENT_RECOVERY_RECORD_ID=prior-env-record\n"
        "W1_N8N_ENCRYPTION_KEY_RECOVERY_RECORD_ID=prior-n8n-key-record\n"
        "W1_RECOVERY_RECORDS_CONFIRMED=no\n"
        "W1_RPO_HOURS=24\n"
        "W1_RTO_HOURS=4\n"
        "W1_T16_RETENTION_DAILY=30\n"
        "W1_OLLAMA_MODEL_DISPOSITION=redownload-reviewed-models\n",
        encoding="utf-8",
    )
    with mock.patch.object(records, "POLICY_PATH", policy):
        records.mark_records_confirmed()
    rendered = policy.read_text(encoding="utf-8")
    assert "W1_RECOVERY_RECORDS_CONFIRMED=yes" in rendered
    assert "W1_ENVIRONMENT_RECOVERY_RECORD_ID=t16-dpapi-cs-ai-lab-env-v1" in rendered


def test_remote_environment_command_uses_only_the_fixed_deployed_env_path():
    with mock.patch.object(records, "configured_target", return_value="configured-target"), mock.patch.object(
        records, "wsl_bash_script_command", side_effect=lambda value: value
    ), mock.patch.object(records, "ssh_command", side_effect=lambda target, command: [target, command]):
        command = records.remote_environment_command()
    assert command[0] == "configured-target"
    assert "cd /home/chris/projects/cs-ai-lab-infra" in command[1]
    assert "cat .env" in command[1]
