import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/capture-w1-recovery-bundle.sh"


def test_capture_refuses_before_env_or_docker_without_approval():
    result = subprocess.run(["bash", str(SCRIPT)], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 2
    assert "without --approve" in result.stderr


def test_capture_requires_explicit_n8n_quiescence_before_env_or_docker():
    result = subprocess.run(["bash", str(SCRIPT), "--approve"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 2
    assert "n8n writes are quiesced" in result.stderr


def test_capture_archives_only_labeled_n8n_volumes_and_uses_full_contract():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "com.docker.compose.project=cs-ai-lab" in source
    assert "com.docker.compose.volume" in source
    assert "create-full-lab" in source
    assert "--require-full-lab" in source
    assert "source .env" in source
