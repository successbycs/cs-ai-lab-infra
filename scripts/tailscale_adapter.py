#!/usr/bin/env python3
"""Governed adapter for the owner-controlled Tailscale tailnet.

The adapter intentionally exposes fixed operations only. It obtains a short-lived
OAuth access token from machine-local credentials, keeps secrets and raw API
responses out of Git and execution logs, and requires an explicit approval flag
for every operation that changes tailnet state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".env.tailscale.local"
POLICY_ROOT = ROOT / "tailscale" / "policies"
CATALOG_PATH = ROOT / "tailscale" / "command-catalog.json"
LOG_PATH = ROOT / ".tailscale-execution.local.jsonl"
API_BASE = "https://api.tailscale.com/api/v2"
OAUTH_TOKEN_URL = f"{API_BASE}/oauth/token"
TOOL_ID = "tailscale_governed"
SAFE_DEVICE_ID = re.compile(r"[0-9]{1,20}\Z")

OPERATIONS = {
    "preflight": {"approval_required": False},
    "list-devices": {"approval_required": False},
    "inspect-policy": {"approval_required": False},
    "validate-policy": {"approval_required": False},
    "apply-policy": {"approval_required": True},
    "set-device-authorization": {"approval_required": True},
}


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256(value: str | bytes) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def read_local_config() -> dict[str, str]:
    values = {key: value for key, value in os.environ.items() if key.startswith("TAILSCALE_")}
    if CONFIG_PATH.is_file():
        for raw in CONFIG_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            if separator and key in {"TAILSCALE_OAUTH_CLIENT_ID", "TAILSCALE_OAUTH_CLIENT_SECRET", "TAILSCALE_TAILNET"}:
                values.setdefault(key, value.strip())
    return values


def config() -> dict[str, str]:
    values = read_local_config()
    required = ("TAILSCALE_OAUTH_CLIENT_ID", "TAILSCALE_OAUTH_CLIENT_SECRET")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise RuntimeError(
            "Missing machine-local Tailscale OAuth configuration: " + ", ".join(missing) + ". "
            "Copy tailscale/.env.tailscale.local.example to .env.tailscale.local; never commit it."
        )
    return {
        "client_id": values["TAILSCALE_OAUTH_CLIENT_ID"],
        "client_secret": values["TAILSCALE_OAUTH_CLIENT_SECRET"],
        "tailnet": values.get("TAILSCALE_TAILNET", "-") or "-",
    }


def oauth_token(settings: dict[str, str]) -> str:
    payload = urlencode({"client_id": settings["client_id"], "client_secret": settings["client_secret"]}).encode("utf-8")
    request = Request(OAUTH_TOKEN_URL, data=payload, method="POST", headers={"content-type": "application/x-www-form-urlencoded"})
    response = request_json(request)
    token = response.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Tailscale OAuth token response did not contain an access token.")
    return token


def request_json(request: Request) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=30) as response:  # nosec B310: fixed HTTPS API base only
            body = response.read().decode("utf-8")
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Tailscale API returned HTTP {error.code}: {body}") from error
    except URLError as error:
        raise RuntimeError(f"Tailscale API request failed: {error.reason}") from error
    try:
        value = json.loads(body)
    except json.JSONDecodeError as error:
        raise RuntimeError("Tailscale API returned invalid JSON.") from error
    if not isinstance(value, dict):
        raise RuntimeError("Tailscale API returned a JSON value that was not an object.")
    return value


def api_request(method: str, path: str, payload: str | None = None, content_type: str = "application/json") -> dict[str, Any]:
    if not path.startswith("/") or ".." in path:
        raise ValueError("API path must be an absolute relative path without '..'.")
    settings = config()
    token = oauth_token(settings)
    data = payload.encode("utf-8") if payload is not None else None
    request = Request(
        f"{API_BASE}{path}",
        data=data,
        method=method,
        headers={"authorization": f"Bearer {token}", "content-type": content_type, "accept": "application/json"},
    )
    return request_json(request)


def tailnet_path(suffix: str) -> str:
    value = config()["tailnet"]
    if value != "-" and not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
        raise ValueError("TAILSCALE_TAILNET must be '-' or a safe tailnet identifier.")
    return f"/tailnet/{value}{suffix}"


def summarise_device(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id", "")),
        "name": item.get("name"),
        "hostname": item.get("hostname"),
        "os": item.get("os"),
        "authorized": item.get("authorized"),
        "connected": item.get("connected"),
        "is_exit_node": item.get("isExitNode"),
        "advertised_routes": item.get("advertisedRoutes", []),
        "tags": item.get("tags", []),
        "created": item.get("created"),
        "expires": item.get("expires"),
    }


def list_devices() -> dict[str, Any]:
    result = api_request("GET", tailnet_path("/devices"))
    devices = result.get("devices")
    if not isinstance(devices, list):
        raise RuntimeError("Tailscale device response did not contain a devices list.")
    return {"device_count": len(devices), "devices": [summarise_device(item) for item in devices if isinstance(item, dict)]}


def inspect_policy() -> dict[str, Any]:
    result = api_request("GET", tailnet_path("/acl"))
    policy = result.get("acl") or result.get("policy") or result
    rendered = json.dumps(policy, sort_keys=True, separators=(",", ":"))
    return {"policy_sha256": sha256(rendered), "policy_bytes": len(rendered), "policy": policy}


def resolve_policy_file(value: str) -> Path:
    candidate = (ROOT / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    root = POLICY_ROOT.resolve()
    if not candidate.is_relative_to(root) or candidate.suffix not in {".hujson", ".json"} or not candidate.is_file():
        raise ValueError("Policy file must be an existing .hujson or .json file inside tailscale/policies.")
    return candidate


def policy_payload(path: Path) -> str:
    payload = path.read_text(encoding="utf-8")
    if not payload.strip():
        raise ValueError("Policy file must not be empty.")
    if len(payload.encode("utf-8")) > 256_000:
        raise ValueError("Policy file exceeds the 256 KB adapter limit.")
    return payload


def validate_policy(path: Path) -> dict[str, Any]:
    payload = policy_payload(path)
    result = api_request("POST", tailnet_path("/acl/validate"), payload, "application/hujson")
    return {"policy_file": str(path.relative_to(ROOT)), "policy_sha256": sha256(payload), "validation": result}


def apply_policy(path: Path) -> dict[str, Any]:
    payload = policy_payload(path)
    validation = validate_policy(path)
    result = api_request("POST", tailnet_path("/acl"), payload, "application/hujson")
    return {"policy_file": str(path.relative_to(ROOT)), "policy_sha256": sha256(payload), "validation": validation["validation"], "apply": result}


def set_device_authorization(device_id: str, authorized: bool) -> dict[str, Any]:
    if not SAFE_DEVICE_ID.fullmatch(device_id):
        raise ValueError("device ID must contain only digits.")
    payload = json.dumps({"authorized": authorized})
    result = api_request("POST", f"/device/{device_id}/authorized", payload)
    return {"device_id": device_id, "authorized": authorized, "result": result}


def append_log(command: str, approved: bool, payload: dict[str, Any]) -> None:
    rendered = json.dumps(payload, sort_keys=True, default=str)
    entry = {"logged_at": now(), "tool_id": TOOL_ID, "command": command, "approved": approved, "payload_sha256": sha256(rendered), "payload_bytes": len(rendered)}
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, separators=(",", ":")) + "\n")


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description="Governed Tailscale tailnet adapter.")
    command_parser.add_argument("command", choices=["describe-requirements", *OPERATIONS])
    command_parser.add_argument("--policy-file")
    command_parser.add_argument("--device-id")
    action = command_parser.add_mutually_exclusive_group()
    action.add_argument("--authorize", action="store_true")
    action.add_argument("--deauthorize", action="store_true")
    command_parser.add_argument("--approve", action="store_true", help="Record explicit approval for a mutating operation.")
    return command_parser


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "describe-requirements":
        payload: dict[str, Any] = {
            "tool_id": TOOL_ID,
            "requirements": [
                "A machine-local Tailscale OAuth client ID and secret with only required scopes.",
                "TAILSCALE_TAILNET set to '-' or the owner tailnet identifier.",
                "Reviewed policy files only inside tailscale/policies.",
                "Explicit operator approval for policy application or device authorization changes.",
            ],
            "recommended_scopes": {
                "read_only": ["devices:core:read", "devices:routes:read", "policy_file:read", "devices:posture_attributes:read"],
                "policy_apply": ["policy_file", "devices:core:read", "devices:posture_attributes:read"],
                "device_authorization": ["devices:core"],
            },
            "mutating_commands": ["apply-policy", "set-device-authorization"],
        }
    else:
        operation = OPERATIONS[args.command]
        if operation["approval_required"] and not args.approve:
            raise PermissionError(f"{args.command} requires --approve after explicit operator approval.")
        if args.command == "preflight":
            settings = config()
            inventory = list_devices()
            payload = {"tool_id": TOOL_ID, "tailnet": settings["tailnet"], "device_count": inventory["device_count"], "ok": True}
        elif args.command == "list-devices":
            payload = {"tool_id": TOOL_ID, **list_devices(), "ok": True}
        elif args.command == "inspect-policy":
            payload = {"tool_id": TOOL_ID, **inspect_policy(), "ok": True}
        elif args.command in {"validate-policy", "apply-policy"}:
            if not args.policy_file:
                raise SystemExit("--policy-file is required for this command.")
            path = resolve_policy_file(args.policy_file)
            operation_result = validate_policy(path) if args.command == "validate-policy" else apply_policy(path)
            payload = {"tool_id": TOOL_ID, **operation_result, "ok": True}
        else:
            if not args.device_id or args.authorize == args.deauthorize:
                raise SystemExit("set-device-authorization requires --device-id and exactly one of --authorize or --deauthorize.")
            payload = {"tool_id": TOOL_ID, **set_device_authorization(args.device_id, args.authorize), "ok": True}
    append_log(args.command, args.approve, payload)
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("ok", True) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, PermissionError) as error:
        print(json.dumps({"tool_id": TOOL_ID, "ok": False, "error": str(error)}), file=sys.stderr)
        raise SystemExit(1)
