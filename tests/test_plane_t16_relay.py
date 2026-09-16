from __future__ import annotations

from scripts import plane_t16_relay


def test_relay_command_is_fixed_and_strict():
    command = plane_t16_relay.ssh_bridge_command("t480", 8090)
    assert command[:3] == ["powershell.exe", "-NoProfile", "-NonInteractive"]
    assert "StrictHostKeyChecking=yes" in command[-1]
    assert "BatchMode=yes" in command[-1]
    assert "-W" not in command[-1]


def test_status_without_state_is_not_running(monkeypatch):
    monkeypatch.setattr(plane_t16_relay, "_state", lambda: None)
    assert plane_t16_relay.status()["status"] == "NOT_RUNNING"
