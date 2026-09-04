import json

import pytest

from scripts import tailscale_adapter


def test_adapter_exposes_only_fixed_operations():
    assert set(tailscale_adapter.OPERATIONS) == {
        "preflight",
        "list-devices",
        "inspect-policy",
        "validate-policy",
        "apply-policy",
        "set-device-authorization",
    }
    assert tailscale_adapter.OPERATIONS["apply-policy"]["approval_required"] is True
    assert tailscale_adapter.OPERATIONS["set-device-authorization"]["approval_required"] is True


def test_local_config_requires_oauth_client_credentials(monkeypatch):
    monkeypatch.setattr(tailscale_adapter, "read_local_config", lambda: {})

    with pytest.raises(RuntimeError, match="TAILSCALE_OAUTH_CLIENT_ID"):
        tailscale_adapter.config()


def test_policy_files_must_be_inside_reviewed_policy_directory(tmp_path, monkeypatch):
    policy_root = tmp_path / "tailscale" / "policies"
    policy_root.mkdir(parents=True)
    approved = policy_root / "reviewed.hujson"
    approved.write_text("{}", encoding="utf-8")
    outside = tmp_path / "outside.hujson"
    outside.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(tailscale_adapter, "ROOT", tmp_path)
    monkeypatch.setattr(tailscale_adapter, "POLICY_ROOT", policy_root)

    assert tailscale_adapter.resolve_policy_file(str(approved)) == approved
    with pytest.raises(ValueError, match="tailscale/policies"):
        tailscale_adapter.resolve_policy_file(str(outside))


def test_apply_policy_validates_the_exact_payload_before_applying(monkeypatch, tmp_path):
    policy = tmp_path / "reviewed.hujson"
    policy.write_text('{"acls":[]}', encoding="utf-8")
    calls = []

    def fake_api_request(method, path, payload=None, content_type="application/json"):
        calls.append((method, path, payload, content_type))
        return {"ok": True}

    monkeypatch.setattr(tailscale_adapter, "api_request", fake_api_request)
    monkeypatch.setattr(tailscale_adapter, "tailnet_path", lambda suffix: "/tailnet/-" + suffix)
    monkeypatch.setattr(tailscale_adapter, "ROOT", tmp_path)

    result = tailscale_adapter.apply_policy(policy)

    assert result["policy_sha256"] == tailscale_adapter.sha256('{"acls":[]}')
    assert calls == [
        ("POST", "/tailnet/-/acl/validate", '{"acls":[]}', "application/hujson"),
        ("POST", "/tailnet/-/acl", '{"acls":[]}', "application/hujson"),
    ]


def test_device_authorization_accepts_only_numeric_device_ids(monkeypatch):
    captured = {}
    monkeypatch.setattr(tailscale_adapter, "api_request", lambda method, path, payload=None, content_type="application/json": captured.update({"method": method, "path": path, "payload": payload}) or {"ok": True})

    result = tailscale_adapter.set_device_authorization("11055", False)

    assert result["authorized"] is False
    assert captured == {"method": "POST", "path": "/device/11055/authorized", "payload": json.dumps({"authorized": False})}
    with pytest.raises(ValueError, match="only digits"):
        tailscale_adapter.set_device_authorization("../../anything", True)


def test_mutations_require_explicit_approval_before_credential_use(monkeypatch):
    monkeypatch.setattr(tailscale_adapter, "config", lambda: pytest.fail("credentials should not be read"))

    with pytest.raises(PermissionError, match="requires --approve"):
        tailscale_adapter.main(["apply-policy", "--policy-file", "tailscale/policies/x.hujson"])
