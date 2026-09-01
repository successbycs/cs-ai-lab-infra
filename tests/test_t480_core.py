import json
from pathlib import Path
import sys
from datetime import datetime

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
from t480_core.core import run_command
from scripts import t480_adapter
from monitoring.health_history import append as append_health_history
from monitoring.health_history import weekly_report


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
    assert "logged_at_nz" in content


def test_command_results_include_nz_time_alongside_utc():
    result = run_command([sys.executable, "-c", ""], timeout_seconds=5)

    assert result["ok"] is True
    assert datetime.fromisoformat(result["started_at"]).tzinfo is not None
    assert datetime.fromisoformat(result["finished_at"]).tzinfo is not None
    assert datetime.fromisoformat(result["started_at_nz"]).tzinfo is not None
    assert datetime.fromisoformat(result["finished_at_nz"]).tzinfo is not None
    assert result["started_at_nz"] != result["started_at"]


def test_configuration_fingerprint_changes_with_content(tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"value":1}', encoding="utf-8")
    first = fingerprint_files([config])
    config.write_text('{"value":2}', encoding="utf-8")
    assert fingerprint_files([config]) != first


def test_healthcheck_stops_when_the_control_path_is_unavailable(monkeypatch):
    control_path = {"tool_id": "t480_wsl_lab", "ok": False, "error": "SSH unavailable"}
    monkeypatch.setattr(t480_adapter, "preflight", lambda: control_path)
    monkeypatch.setattr(t480_adapter, "execute", lambda *_args, **_kwargs: pytest.fail("lab health should not run"))

    result = t480_adapter.healthcheck()

    assert result["ok"] is False
    assert result["checks"] == {"control_path": control_path}


def test_healthcheck_runs_lab_health_after_a_control_path_pass(monkeypatch):
    control_path = {
        "tool_id": "t480_wsl_lab",
        "ok": True,
        "remote_check": {"started_at": "2026-08-30T22:00:00+00:00", "duration_ms": 1},
    }
    lab_health = {
        "tool_id": "t480_wsl_lab",
        "operation": "lab_health",
        "ok": True,
        "result": {
            "stdout": "OK           postgres           running and healthy\nRESULT   PASS               all required checks passed\n",
            "finished_at": "2026-08-30T22:00:01+00:00",
        },
    }
    published = {"operation": "healthcheck_publish", "ok": True, "result": {"duration_ms": 2}}
    monkeypatch.setattr(t480_adapter, "preflight", lambda: control_path)
    startup = {"ok": True, "result": {"stdout": '{"present":true}', "duration_ms": 1}}
    firewall = {"ok": True, "result": {"stdout": '{"present":true}', "duration_ms": 1}}
    monkeypatch.setattr(
        t480_adapter,
        "execute",
        lambda operation, approved: lab_health if operation == "lab_health" else startup if operation == "startup_status" else firewall,
    )
    monkeypatch.setattr(t480_adapter, "publish_healthcheck", lambda summary: published)
    monkeypatch.setattr(t480_adapter, "record_local_healthcheck", lambda summary: {"history_records": 1, "state_transitions": 1})

    result = t480_adapter.healthcheck()

    assert result["ok"] is True
    assert result["checks"] == {
        "control_path": control_path,
        "lab_health": lab_health,
        "startup_task": startup,
        "dashboard_firewall": firewall,
        "dashboard_publish": published,
    }
    assert result["summary"]["overall_status"] == "PASS"
    assert result["summary"]["checks"][1]["key"] == "postgres"


def test_healthcheck_command_is_case_insensitive():
    assert t480_adapter.parser().parse_args(["Healthcheck"]).command == "healthcheck"
    assert t480_adapter.parser().parse_args(["Healthreport"]).command == "healthreport"


def test_healthcheck_summary_does_not_copy_raw_command_output():
    summary = t480_adapter.normalise_healthcheck(
        {"ok": True, "remote_check": {"started_at": "2026-08-30T22:00:00+00:00"}},
        {
            "ok": True,
            "result": {
                "stdout": "OK           postgres           password=must-not-be-published\n",
                "finished_at": "2026-08-30T22:00:01+00:00",
            },
        },
    )

    rendered = json.dumps(summary)
    assert "must-not-be-published" not in rendered
    assert summary["checks"][1]["detail"] == "PostgreSQL service readiness or query capability was checked."


def test_healthcheck_publisher_uses_only_fixed_database_and_rendering_commands(monkeypatch):
    captured = {}

    def fake_execute(operation, **_kwargs):
        captured["operation"] = operation
        return {"operation": operation.operation_id, "result": {"ok": True}, "ok": True}

    monkeypatch.setattr(t480_adapter, "configured_target", lambda: "t480")
    monkeypatch.setattr(t480_adapter, "execute_operation", fake_execute)
    result = t480_adapter.publish_healthcheck({"overall_status": "PASS", "checks": []})

    assert result["ok"] is True
    assert captured["operation"].operation_id == "healthcheck_publish"
    assert "monitoring.record_healthcheck" in captured["operation"].wsl_script
    assert "monitoring.health_dashboard_payload" in captured["operation"].wsl_script
    assert "render_health_dashboard.py" in captured["operation"].wsl_script


def test_dashboard_is_required_by_compose_healthcheck_and_t480_startup_paths():
    compose = Path("compose.yaml").read_text(encoding="utf-8")
    health_check = Path("scripts/health-check.sh").read_text(encoding="utf-8")

    assert "health_dashboard:" in compose
    assert "restart: unless-stopped" in compose
    assert "health_dashboard" in health_check
    assert "health_dashboard" in t480_adapter.OPERATIONS["lab_services_start"]["wsl_script"]
    assert "health_dashboard" in t480_adapter.OPERATIONS["startup_enable"]["command"]
    assert "health_dashboard" in t480_adapter.OPERATIONS["m5_boot_startup_enable"]["command"]


def test_dashboard_firewall_operations_are_fixed_and_private_profile_only():
    status = t480_adapter.OPERATIONS["health_dashboard_firewall_status"]
    enable = t480_adapter.OPERATIONS["health_dashboard_firewall_enable"]

    assert status["approval_required"] is False
    assert enable["approval_required"] is True
    assert "LocalPort 8080" in enable["command"]
    assert "-Profile Private" in enable["command"]
    assert "New-NetFirewallRule" in enable["command"]


def test_repository_snapshot_recovery_creates_a_patch_before_tracked_reset():
    operation = t480_adapter.OPERATIONS["repository_snapshot_and_update"]
    script = operation["wsl_script"]

    assert operation["approval_required"] is True
    assert "git diff --binary HEAD" in script
    assert "git apply --check --reverse" in script
    assert "sha256sum" in script
    assert "git reset --hard origin/main" in script
    assert "git clean" not in script


def test_health_history_is_redacted_rotated_and_emits_transition_only(tmp_path):
    history = tmp_path / "history.jsonl"
    latest = tmp_path / "latest.json"
    transitions = tmp_path / "transitions.jsonl"
    summary = {"overall_status": "PASS", "checks": [{"key": "postgres", "status": "PASS", "detail": "safe"}]}

    first = append_health_history(summary, history_path=history, latest_path=latest, transitions_path=transitions)
    second = append_health_history(summary, history_path=history, latest_path=latest, transitions_path=transitions)

    assert first["state_transitions"] == 2
    assert second["state_transitions"] == 0
    assert len(history.read_text(encoding="utf-8").splitlines()) == 2
    assert len(transitions.read_text(encoding="utf-8").splitlines()) == 1


def test_weekly_health_report_uses_local_history_only(tmp_path):
    history = tmp_path / "history.jsonl"
    latest = tmp_path / "latest.json"
    transitions = tmp_path / "transitions.jsonl"
    append_health_history(
        {"overall_status": "WARN", "checks": []},
        history_path=history,
        latest_path=latest,
        transitions_path=transitions,
    )
    output = tmp_path / "weekly.md"
    report = weekly_report(history, output)

    assert report["runs"] == 1
    assert report["counts"]["WARN"] == 1
    assert "weekly Healthcheck report" in output.read_text(encoding="utf-8")


def test_healthcheck_scheduler_design_is_disabled_and_safe():
    schedule = json.loads(Path("monitoring/healthcheck-schedule.json").read_text(encoding="utf-8"))

    assert schedule["enabled"] is False
    assert schedule["command"][-1] == "Healthcheck"
    assert schedule["report_command"][-1] == "Healthreport"
    assert schedule["safety"] == {
        "contains_credentials": False,
        "allows_service_mutation": False,
        "outbound_notifications": False,
        "activation_requires_separate_approval": True,
    }
