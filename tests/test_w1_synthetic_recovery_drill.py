import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/w1-synthetic-recovery-drill.sh"


def test_drill_refuses_to_run_without_explicit_approval_before_docker():
    result = subprocess.run(["bash", str(SCRIPT)], text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 2
    assert "without --approve" in result.stderr
    assert "docker" not in result.stdout.lower()


def test_drill_requires_a_test_only_encryption_key_before_docker():
    result = subprocess.run(["bash", str(SCRIPT), "--approve"], text=True, capture_output=True, cwd=ROOT)
    assert result.returncode == 2
    assert "test-only encryption-key file" in result.stderr


def test_drill_uses_isolated_projects_volumes_and_no_env_loading():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "--project-name" in source
    assert "w1_source_" in source and "w1_restore_" in source
    assert "n8n_data" in source and "n8n_files" in source
    assert "source .env" not in source
    assert "test-only-preserved-not-recorded" in source
    assert "wait_for_service" in source
    assert 'restore_postgres_ready wait_for_service "$restore_project" postgres pg_isready' in source
    assert 'restore_n8n_data docker run --rm --user 0:0' in source
    assert 'restore_n8n_files docker run --rm --user 0:0' in source
    assert 'pg_dump --clean --if-exists' in source


def write_bundle(bundle: Path):
    probes = (
        "source_start", "source_health", "source_synthetic_file", "source_dump", "archive_n8n_data", "archive_n8n_files",
        "restore_postgres_start", "restore_postgres_ready", "restore_database", "restore_n8n_data", "restore_n8n_files", "restored_n8n_start", "restored_n8n_health",
    )
    bundle.mkdir()
    (bundle / "manifest.txt").write_text(
        "schema_version=cs-ai-lab.w1-synthetic-recovery.v1\n"
        "source_project=w1_source_20260907t120000z\n"
        "restore_project=w1_restore_20260907t120000z\n"
        "encryption_key=test-only-preserved-not-recorded\n",
        encoding="utf-8",
    )
    for probe in probes:
        (bundle / f"{probe}.txt").write_text(f"probe: {probe}\nexit_code: 0\n", encoding="utf-8")
    for name in ("postgres.sql.gz", "n8n-data.tar.gz", "n8n-files.tar.gz"):
        (bundle / name).write_bytes(b"synthetic")
    files = ["manifest.txt", *(f"{probe}.txt" for probe in probes), "postgres.sql.gz", "n8n-data.tar.gz", "n8n-files.tar.gz"]
    with (bundle / "SHA256SUMS").open("w", encoding="utf-8") as handle:
        for name in files:
            output = subprocess.check_output(["sha256sum", name], cwd=bundle, text=True)
            handle.write(output)


def test_evidence_verifier_accepts_complete_synthetic_bundle(tmp_path: Path):
    bundle = tmp_path / "bundle"
    write_bundle(bundle)
    result = subprocess.run(
        ["bash", "scripts/verify-w1-synthetic-recovery-evidence.sh", str(bundle)], text=True, capture_output=True, cwd=ROOT
    )
    assert result.returncode == 0, result.stderr
    assert "verified" in result.stdout


def test_evidence_verifier_rejects_tampered_synthetic_bundle(tmp_path: Path):
    bundle = tmp_path / "bundle"
    write_bundle(bundle)
    (bundle / "postgres.sql.gz").write_bytes(b"tampered")
    result = subprocess.run(
        ["bash", "scripts/verify-w1-synthetic-recovery-evidence.sh", str(bundle)], text=True, capture_output=True, cwd=ROOT
    )
    assert result.returncode != 0
