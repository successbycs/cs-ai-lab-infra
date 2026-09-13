import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_registry_example_validates():
    result = subprocess.run([sys.executable, "scripts/validate_project_registry.py"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "projects=2" in result.stdout

def test_static_template_is_private_by_default():
    compose = (ROOT / "templates/static-web/compose.yaml").read_text()
    ingress = (ROOT / "templates/static-web/compose.private-ingress.yaml").read_text()
    assert "ports:" not in compose
    assert "COMPOSE_PROJECT_NAME" in compose
    assert "WEB_IMAGE" in compose
    assert "restart: unless-stopped" in compose
    assert "pids:" in compose
    assert "max-size" in compose
    assert "127.0.0.1" in ingress

def test_registry_does_not_contain_secret_values():
    registry = json.loads((ROOT / "projects/registry.example.json").read_text())
    assert all("password" not in json.dumps(project).lower() for project in registry["projects"])

def test_registry_rejects_unknown_or_incomplete_project_fields(tmp_path):
    registry = json.loads((ROOT / "projects/registry.example.json").read_text())
    registry["projects"][0]["credential_value"] = "forbidden"
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry))
    result = subprocess.run([sys.executable, "scripts/validate_project_registry.py", str(path)], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 2
