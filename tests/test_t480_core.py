import base64
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
    build_wsl_powershell_command,
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


def test_wsl_wrapper_propagates_the_wsl_process_exit_code():
    rendered = build_wsl_powershell_command("exit 7", TransportSettings())

    assert rendered.endswith("exit $LASTEXITCODE")


def test_wsl_script_reader_cannot_steal_following_commands():
    import subprocess
    from t480_core import build_wsl_powershell_command

    script = "printf 'before\\n'\ncat >/dev/null\nprintf 'after\\n'\nexit 7\n"
    wrapper = build_wsl_powershell_command(script, TransportSettings())
    bash_command = wrapper.split(" -- bash -c '", 1)[1].split("';", 1)[0]
    result = subprocess.run(['bash', '-c', bash_command], input=base64.b64encode(script.encode()), capture_output=True)
    assert result.stdout == b'before\nafter\n'
    assert result.returncode == 7


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
    assert "gzip -d" in captured["operation"].wsl_script
    assert "printf '%s\\n' \"$record_sql\" | docker compose exec" in captured["operation"].wsl_script


def test_dashboard_is_required_by_health_checks_but_boot_starts_the_minimum_dependency_chain():
    compose = Path("compose.yaml").read_text(encoding="utf-8")
    health_check = Path("scripts/health-check.sh").read_text(encoding="utf-8")

    assert "health_dashboard:" in compose
    assert "restart: unless-stopped" in compose
    assert "health_dashboard" in health_check
    assert "health_dashboard" in t480_adapter.OPERATIONS["lab_services_start"]["wsl_script"]
    for operation_id in ("startup_enable", "m5_boot_startup_enable"):
        command = t480_adapter.OPERATIONS[operation_id]["command"]
        assert "docker compose up -d n8n;" in command
        assert "docker compose up -d n8n health_dashboard" not in command


def test_m5_backup_status_is_fixed_read_only_manifest_verification():
    operation = t480_adapter.OPERATIONS["m5_backup_status"]
    script = operation["wsl_script"]
    assert operation["approval_required"] is False
    assert "find postgres/backup" in script
    assert "backup_manifest.py verify" in script
    assert "M5_BACKUP_VERIFY_OK" in script
    assert "pg_dump" not in script and "docker compose up" not in script


def test_dashboard_firewall_operations_are_fixed_and_private_profile_only():
    status = t480_adapter.OPERATIONS["health_dashboard_firewall_status"]
    enable = t480_adapter.OPERATIONS["health_dashboard_firewall_enable"]

    assert status["approval_required"] is False
    assert enable["approval_required"] is True
    assert "LocalPort 8080" in enable["command"]
    assert "-Profile Private" in enable["command"]
    assert "New-NetFirewallRule" in enable["command"]


def test_tailscale_installer_is_fixed_signed_and_does_not_enrol_or_expose_the_host():
    status = t480_adapter.OPERATIONS["tailscale_windows_status"]
    install = t480_adapter.OPERATIONS["tailscale_windows_install"]

    assert status["approval_required"] is False
    assert install["approval_required"] is True
    assert "https://dl.tailscale.com/stable/tailscale-setup-1.102.3-amd64.msi" in install["command"]
    assert "Get-AuthenticodeSignature" in install["command"]
    assert "msiexec.exe" in install["command"]
    assert "TS_NOLAUNCH=1" in install["command"]
    assert "tailscale up" not in install["command"]
    assert "advertise-routes" not in install["command"]
    assert "advertise-exit-node" not in install["command"]


def test_tailscale_peer_inventory_is_read_only():
    operation = t480_adapter.OPERATIONS["tailscale_tailnet_peers"]

    assert operation["approval_required"] is False
    assert "status --json" in operation["command"]
    assert "ExitNode" in operation["command"]
    assert "tailscale up" not in operation["command"]


def test_performance_diagnostics_is_fixed_and_read_only():
    operation = t480_adapter.OPERATIONS["performance_diagnostics"]

    assert operation["approval_required"] is False
    assert "Get-Process" in operation["command"]
    assert "TermService" in operation["command"]
    assert "Get-NetTCPConnection -LocalPort 3389" in operation["command"]
    assert "Restart-Service" not in operation["command"]
    assert "Stop-Process" not in operation["command"]


def test_network_profile_status_is_read_only():
    operation = t480_adapter.OPERATIONS["network_profile_status"]

    assert operation["approval_required"] is False
    assert "Get-NetConnectionProfile" in operation["command"]


def test_security_sweep_operations_are_fixed_and_read_only():
    operation_ids = {
        "security_windows_baseline",
        "security_defender_status",
        "security_accounts_and_shares",
        "security_network_exposure",
        "security_sensitive_firewall_rules",
        "security_remote_access",
        "security_persistence",
        "security_persistence_signatures",
        "security_services",
        "security_wmi_powershell",
        "security_software_inventory",
        "security_risky_file_metadata",
        "security_wsl_posture",
    }
    forbidden = (
        "Start-MpScan",
        "Remove-MpThreat",
        "Set-MpPreference",
        "Add-MpPreference",
        "Set-ItemProperty",
        "New-Item",
        "Remove-Item",
        "Start-Service",
        "Stop-Service",
        "Restart-Service",
        "apt-get update",
        "apt-get upgrade",
        "docker compose up",
        "docker restart",
    )

    for operation_id in operation_ids:
        operation = t480_adapter.OPERATIONS[operation_id]
        command = operation.get("command", "") + operation.get("wsl_script", "")
        assert operation["approval_required"] is False
        assert not any(token in command for token in forbidden)


def test_windows_security_sweep_operations_fit_the_ssh_command_line():
    for operation_id, operation in t480_adapter.OPERATIONS.items():
        if not operation_id.startswith("security_") or "command" not in operation:
            continue
        encoded = base64.b64encode(operation["command"].encode("utf-16-le"))
        assert len(encoded) < 7_000, operation_id


def test_risky_file_sweep_is_bounded_and_does_not_read_document_content():
    command = t480_adapter.OPERATIONS["security_risky_file_metadata"]["command"]

    assert "Select-Object -First 300" in command
    assert "Get-AuthenticodeSignature" in command
    assert "Get-FileHash" in command
    assert "Get-Content" not in command
    assert "Get-MpThreatDetection" not in command
    assert "Join-Path $env:USERPROFILE 'Downloads'" in command


def test_network_security_sweep_limits_firewall_rule_output():
    command = t480_adapter.OPERATIONS["security_network_exposure"]["command"]

    assert "Select-Object -First 60" in command
    assert "Select-Object -First 100" in command
    assert "enabled_inbound_allow_rule_count" in command


def test_dashboard_windows_probe_checks_only_listener_and_local_health():
    operation = t480_adapter.OPERATIONS["health_dashboard_windows_probe"]

    assert operation["approval_required"] is False
    assert "Get-NetTCPConnection" in operation["command"]
    assert "127.0.0.1:8080/healthz" in operation["command"]


def test_dashboard_lan_proxy_is_private_and_fixed_to_loopback_dashboard():
    operation = t480_adapter.OPERATIONS["health_dashboard_lan_proxy_enable"]

    assert operation["approval_required"] is True
    assert "NetworkCategory -eq 'Private'" in operation["command"]
    assert "connectaddress=127.0.0.1 connectport=8080" in operation["command"]
    assert "netsh.exe interface portproxy add v4tov4" in operation["command"]
    assert "0.0.0.0" not in operation["command"]


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
