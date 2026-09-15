import subprocess
import os
from pathlib import Path
from contextlib import contextmanager


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/capture-w1-recovery-bundle.sh"
PAUSE = ROOT / "BACKUPS-PAUSED.md"


@contextmanager
def backup_creation_enabled_for_test():
    held = ROOT / ".BACKUPS-PAUSED.test-hold"
    PAUSE.rename(held)
    try:
        yield
    finally:
        held.rename(PAUSE)


def test_capture_refuses_before_env_or_docker_without_approval():
    with backup_creation_enabled_for_test():
        result = subprocess.run(["bash", str(SCRIPT)], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 2
    assert "without --approve" in result.stderr


def test_capture_requires_explicit_n8n_quiescence_before_env_or_docker():
    with backup_creation_enabled_for_test():
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


def test_capture_rejects_running_n8n_despite_operator_flag(tmp_path):
    docker = tmp_path / 'docker'
    docker.write_text('#!/bin/sh\nprintf "running-container\\n"\n')
    docker.chmod(0o755)
    with backup_creation_enabled_for_test():
        result = subprocess.run(['bash', str(SCRIPT), '--approve', '--n8n-quiesced'],
            env={**os.environ, 'PATH': str(tmp_path) + ':' + os.environ['PATH']}, capture_output=True, text=True)
    assert result.returncode == 2
    assert 'n8n is still running' in result.stderr
