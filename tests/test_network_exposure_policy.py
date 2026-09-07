from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_exposure_policy_matches_the_checked_in_compose_defaults():
    policy = (ROOT / "docs" / "network-exposure.md").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "POSTGRES_BIND_ADDRESS=127.0.0.1" in env_example
    assert "N8N_BIND_ADDRESS=127.0.0.1" in env_example
    assert "HEALTH_DASHBOARD_BIND_ADDRESS=0.0.0.0" in env_example
    assert '"${POSTGRES_BIND_ADDRESS:-127.0.0.1}:5432:5432"' in compose
    assert '"${N8N_BIND_ADDRESS}:5678:5678"' in compose
    assert '"${HEALTH_DASHBOARD_BIND_ADDRESS:-0.0.0.0}:${HEALTH_DASHBOARD_PORT:-8080}:8080"' in compose
    for binding in ("`127.0.0.1:5432`", "`127.0.0.1:5678`", "`0.0.0.0:8080`"):
        assert binding in policy


def test_wave_zero_docs_do_not_publish_a_private_postgres_endpoint():
    documentation = [
        ROOT / "README.md",
        ROOT / "docs" / "architecture.md",
        ROOT / "docs" / "setup.md",
        ROOT / "docs" / "operations.md",
        ROOT / "docs" / "network-exposure.md",
        ROOT / "postgres" / "README.md",
    ]
    published = "\n".join(path.read_text(encoding="utf-8") for path in documentation)

    assert "192.168.0.210" not in published
    assert "postgresql://192.168" not in published
    assert "docker compose port" in published
