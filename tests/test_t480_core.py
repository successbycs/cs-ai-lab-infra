import json
from pathlib import Path

import pytest

from t480_core import (
    Operation,
    TransportSettings,
    append_execution_log,
    build_ssh_command,
    fingerprint_files,
    load_transport_settings,
    validate_catalog,
)


def test_repository_transport_configuration_is_valid():
    settings = load_transport_settings(Path("t480/transport-config.json"))
    assert settings.wsl_distribution == "Ubuntu"
    assert settings.strict_host_key_checking is True
    assert settings.batch_mode is True


@pytest.mark.parametrize("field", ["strict_host_key_checking", "batch_mode"])
def test_transport_security_controls_cannot_be_disabled(field):
    values = {
        "schema_version": "cs-ai-lab.t480.transport.v1",
        "ssh_target_env": "T480_SSH_TARGET",
        "wsl_distribution": "Ubuntu",
        "connect_timeout_seconds": 10,
        "command_timeout_seconds": 30,
        "long_command_timeout_seconds": 14400,
        "strict_host_key_checking": True,
        "batch_mode": True,
    }
    values[field] = False
    with pytest.raises(ValueError):
        TransportSettings.from_mapping(values)


def test_ssh_command_always_enforces_batch_and_strict_host_key_modes():
    command = build_ssh_command("t480", "Write-Output ok", TransportSettings())
    rendered = " ".join(command)
    assert "BatchMode=yes" in rendered
    assert "StrictHostKeyChecking=yes" in rendered
    assert "ConnectTimeout=10" in rendered


def test_catalog_must_match_code_operations(tmp_path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps({"operations": [{"id": "health", "approval_required": False}]}),
        encoding="utf-8",
    )
    validate_catalog(
        catalog,
        {"health": Operation("health", "Inspect health", powershell_command="Write-Output ok")},
    )
    with pytest.raises(ValueError):
        validate_catalog(catalog, {})


def test_execution_log_retains_hashes_not_remote_output(tmp_path):
    log_path = tmp_path / "execution.jsonl"
    payload = {
        "ok": True,
        "result": {
            "stdout": "sensitive remote detail",
            "stderr": "",
            "exit_code": 0,
            "ok": True,
        },
    }
    append_execution_log(
        log_path,
        tool_id="test",
        command_name="execute",
        operation_id="health",
        payload=payload,
    )
    content = log_path.read_text(encoding="utf-8")
    assert "sensitive remote detail" not in content
    assert "stdout_sha256" in content


def test_configuration_fingerprint_changes_with_content(tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"value":1}', encoding="utf-8")
    first = fingerprint_files([config])
    config.write_text('{"value":2}', encoding="utf-8")
    assert fingerprint_files([config]) != first
