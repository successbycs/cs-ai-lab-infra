from __future__ import annotations

from pathlib import Path
import pytest

from scripts import plane_adapter


def write_env(path: Path, rows: str) -> Path:
    path.write_text(rows, encoding="utf-8")
    path.chmod(0o600)
    return path


def test_config_rejects_non_private_file(tmp_path: Path):
    path = write_env(tmp_path / "plane-access.local.env", "PLANE_ORIGIN=http://plane:8090\nPLANE_WORKSPACE_SLUG=forex\nPLANE_API_KEY_FILE=/tmp/token\nPLANE_API_KEY_VARIABLE=PLANE_API_KEY\n")
    path.chmod(0o644)
    with pytest.raises(plane_adapter.PlaneAccessError, match="mode 0600"):
        plane_adapter.load_config(path)


def test_config_and_referenced_token_are_secret_safe(tmp_path: Path):
    token = write_env(tmp_path / "token.env", "PLANE_API_KEY=private-token\n")
    config = write_env(tmp_path / "plane-access.local.env", f"PLANE_ORIGIN=http://plane:8090\nPLANE_WORKSPACE_SLUG=forex\nPLANE_API_KEY_FILE={token}\nPLANE_API_KEY_VARIABLE=PLANE_API_KEY\n")
    settings = plane_adapter.load_config(config)
    assert settings["PLANE_ORIGIN"] == "http://plane:8090"
    assert plane_adapter.load_token(settings) == "private-token"


def test_browser_requires_explicit_approval(monkeypatch):
    monkeypatch.setattr(plane_adapter, "load_config", lambda: pytest.fail("configuration should not be read"))
    assert plane_adapter.main(["open-browser"]) == 2


def test_projects_response_rejects_bad_shape(monkeypatch):
    monkeypatch.setattr(plane_adapter, "_powershell_json", lambda script: {})
    with pytest.raises(plane_adapter.PlaneAccessError, match="unexpected shape"):
        plane_adapter.list_projects({"PLANE_ORIGIN": "http://plane:8090", "PLANE_WORKSPACE_SLUG": "forex", "PLANE_API_KEY_FILE": "/unused", "PLANE_API_KEY_VARIABLE": "PLANE_API_KEY"})
