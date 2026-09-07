import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIRECTORY = ROOT / "t480" / "evidence-contracts"
VERIFIER = ROOT / "scripts" / "verify-m2-evidence.sh"


def contract(contract_id: str) -> dict[str, str]:
    return json.loads((CONTRACT_DIRECTORY / f"{contract_id}.json").read_text(encoding="utf-8"))


def write_bundle(directory: Path, contract_id: str | None) -> None:
    selected_contract = contract(contract_id or "m2-legacy-n8n-1.118.1")
    files = {
        "manifest.txt": "milestone=M2\n" + (f"evidence_contract={contract_id}\n" if contract_id else ""),
        "configured_images.txt": f"{selected_contract['postgres_image_prefix']}fixture\n{selected_contract['n8n_image']}\nexit_code: 0\n",
        "image_ids.txt": "image-id-fixture\nexit_code: 0\n",
        "compose_ps.txt": "postgres running\nn8n running\nexit_code: 0\n",
        "health_check.txt": "RESULT PASS\nexit_code: 0\n",
        "n8n_health.txt": "ok\nexit_code: 0\n",
        "postgres_pgvector.txt": "vector\nexit_code: 0\n",
        "postgres_vector_distance.txt": "1.41421356237\nexit_code: 0\n",
    }
    for name, content in files.items():
        (directory / name).write_text(content, encoding="utf-8")
    checksums = "".join(
        f"{hashlib.sha256(content.encode()).hexdigest()}  {name}\n" for name, content in files.items()
    )
    (directory / "SHA256SUMS").write_text(checksums, encoding="utf-8")


def verify(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(VERIFIER), str(directory)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_current_evidence_contract_matches_every_compose_n8n_image():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    images = re.findall(r"^\s*image:\s*(n8nio/n8n:[^\s]+)\s*$", compose, flags=re.MULTILINE)

    assert images
    assert set(images) == {contract("m2-current-n8n-1.123.76")["n8n_image"]}


def test_current_contract_fixture_passes_the_m2_verifier(tmp_path):
    bundle = tmp_path / "current"
    bundle.mkdir()
    write_bundle(bundle, "m2-current-n8n-1.123.76")

    result = verify(bundle)

    assert result.returncode == 0, result.stderr
    assert "contract m2-current-n8n-1.123.76" in result.stdout


def test_legacy_contract_fixture_and_unversioned_legacy_bundle_pass(tmp_path):
    versioned = tmp_path / "legacy-versioned"
    versioned.mkdir()
    write_bundle(versioned, "m2-legacy-n8n-1.118.1")
    unversioned = tmp_path / "legacy-unversioned"
    unversioned.mkdir()
    write_bundle(unversioned, None)

    versioned_result = verify(versioned)
    unversioned_result = verify(unversioned)

    assert versioned_result.returncode == 0, versioned_result.stderr
    assert unversioned_result.returncode == 0, unversioned_result.stderr
    assert "contract m2-legacy-n8n-1.118.1" in versioned_result.stdout
    assert "contract m2-legacy-n8n-1.118.1" in unversioned_result.stdout


def test_verifier_rejects_an_unknown_evidence_contract(tmp_path):
    bundle = tmp_path / "unknown-contract"
    bundle.mkdir()
    write_bundle(bundle, "m2-current-n8n-1.123.76")
    manifest = bundle / "manifest.txt"
    manifest.write_text("milestone=M2\nevidence_contract=not-reviewed\n", encoding="utf-8")
    files = [path for path in bundle.iterdir() if path.name != "SHA256SUMS"]
    (bundle / "SHA256SUMS").write_text(
        "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in sorted(files)),
        encoding="utf-8",
    )

    result = verify(bundle)

    assert result.returncode != 0
    assert "Unknown M2 evidence contract: not-reviewed" in result.stderr
