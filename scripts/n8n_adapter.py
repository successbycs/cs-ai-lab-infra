#!/usr/bin/env python3
"""Governed T16-to-T480 adapter for the private n8n instance.

Adapted from the operational n8n adapter in successbycs/Autonomous-Framework
(source commit 174226df8bec1407d8e4b2aab48f184005d436bf).  This version keeps
the n8n API key on the T480 and routes every request through the proven SSH/WSL
transport instead of assuming n8n is reachable from the T16.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

try:  # Supports both `python3 scripts/n8n_adapter.py` and unit-test imports.
    from scripts.t480_adapter import configured_target, run_command, ssh_command, wsl_bash_script_command
except ModuleNotFoundError:  # pragma: no cover - used by direct script execution.
    from t480_adapter import configured_target, run_command, ssh_command, wsl_bash_script_command

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_ROOT = ROOT / "n8n" / "workflows"
LOG_PATH = ROOT / ".n8n-execution.local.jsonl"
TOOL_ID = "n8n_t480"
DEFAULT_BASE_URL = "http://127.0.0.1:5678"
DEFAULT_KEY_FILE = "/home/chris/.config/cs-ai-lab/n8n-api-key"
REMOTE_WORKFLOW_ROOT = "/home/chris/projects/cs-ai-lab-infra/n8n/workflows"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def config() -> dict[str, str]:
    """Configuration is intentionally non-secret; the API key remains on T480."""
    return {"base_url": DEFAULT_BASE_URL, "key_file": DEFAULT_KEY_FILE}


def api_script(method: str, path: str, payload: dict[str, Any] | None = None) -> str:
    if not path.startswith("/") or ".." in path:
        raise ValueError("n8n API path must be an absolute API-relative path without '..'.")
    encoded_payload = base64.b64encode(json.dumps(payload or {}, separators=(",", ":")).encode("utf-8")).decode("ascii")
    settings = config()
    return f"""set -euo pipefail
key_file={shell_quote(settings['key_file'])}
base_url={shell_quote(settings['base_url'])}
payload_file="$(mktemp)"
trap 'rm -f "$payload_file"' EXIT
if [[ ! -r "$key_file" ]]; then
  printf 'n8n API key file is absent or unreadable on T480.\\n' >&2
  exit 3
fi
printf %s {shell_quote(encoded_payload)} | base64 -d > "$payload_file"
curl --fail-with-body --silent --show-error --max-time 60 \\
  -X {shell_quote(method.upper())} \\
  -H 'accept: application/json' \\
  -H 'content-type: application/json' \\
  -H "X-N8N-API-KEY: $(<"$key_file")" \\
  --data-binary @"$payload_file" \\
  "$base_url/api/v1{path}"
"""


def execute_remote(script: str) -> dict[str, Any]:
    result = run_command(ssh_command(configured_target(), wsl_bash_script_command(script)))
    return result


def result_json(result: dict[str, Any]) -> dict[str, Any]:
    if not result["ok"]:
        raise RuntimeError(result["stderr"] or result["stdout"] or "T480 n8n request failed")
    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError as error:
        raise RuntimeError("n8n did not return a JSON object") from error
    if not isinstance(payload, dict):
        raise RuntimeError("n8n returned JSON that was not an object")
    return payload


def api_request(method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    result = execute_remote(api_script(method, path, payload))
    return result_json(result), result


def api_file_script(method: str, path: str, remote_file: str, expected_sha256: str) -> str:
    """Submit an already-deployed workflow without expanding it into the SSH command line."""
    if not path.startswith("/") or ".." in path:
        raise ValueError("n8n API path must be an absolute API-relative path without '..'.")
    remote_path = Path(remote_file)
    if not remote_path.is_relative_to(Path(REMOTE_WORKFLOW_ROOT)) or remote_path.suffix != ".json":
        raise ValueError("Remote workflow file must be inside the deployed n8n/workflows directory.")
    settings = config()
    return f"""set -euo pipefail
key_file={shell_quote(settings['key_file'])}
base_url={shell_quote(settings['base_url'])}
workflow_file={shell_quote(remote_file)}
expected_sha256={shell_quote(expected_sha256)}
if [[ ! -r "$key_file" || ! -r "$workflow_file" ]]; then
  printf 'n8n API key or deployed workflow file is absent or unreadable on T480.\\n' >&2
  exit 3
fi
test "$(sha256sum "$workflow_file" | awk '{{print $1}}')" = "$expected_sha256"
curl --fail-with-body --silent --show-error --max-time 60 \\
  -X {shell_quote(method.upper())} \\
  -H 'accept: application/json' \\
  -H 'content-type: application/json' \\
  -H "X-N8N-API-KEY: $(<"$key_file")" \\
  --data-binary @"$workflow_file" \\
  "$base_url/api/v1{path}"
"""


def api_file_request(method: str, path: str, remote_file: str, expected_sha256: str) -> tuple[dict[str, Any], dict[str, Any]]:
    result = execute_remote(api_file_script(method, path, remote_file, expected_sha256))
    return result_json(result), result


def resolve_workflow(value: str) -> Path:
    candidate = (ROOT / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    if not candidate.is_relative_to(WORKFLOW_ROOT.resolve()):
        raise ValueError("Workflow files must be inside n8n/workflows.")
    if candidate.suffix != ".json" or not candidate.is_file():
        raise ValueError("Workflow file must be an existing JSON file.")
    return candidate


def load_workflow(value: str) -> tuple[Path, dict[str, Any]]:
    path = resolve_workflow(value)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Workflow JSON must be an object.")
    name = str(payload.get("name") or "").strip()
    nodes = payload.get("nodes")
    connections = payload.get("connections")
    if not name or not isinstance(nodes, list) or not isinstance(connections, dict):
        raise ValueError("Workflow requires name, nodes array, and connections object.")
    return path, payload


def workflow_api_payload(workflow: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": workflow["name"],
        "nodes": workflow["nodes"],
        "connections": workflow["connections"],
        "settings": workflow.get("settings", {}),
    }


def list_workflows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload, result = api_request("GET", "/workflows?limit=250")
    records = payload.get("data", payload.get("workflows", []))
    if not isinstance(records, list):
        raise RuntimeError("n8n workflow list did not contain a list.")
    return [record for record in records if isinstance(record, dict)], result


def upsert_workflow(workflow_file: str, activate: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    local_file, workflow = load_workflow(workflow_file)
    remote_file = str(Path(REMOTE_WORKFLOW_ROOT) / local_file.name)
    expected_sha256 = hashlib.sha256(local_file.read_bytes()).hexdigest()
    workflows, _ = list_workflows()
    existing = next((item for item in workflows if item.get("name") == workflow["name"]), None)
    if existing:
        workflow_id = str(existing.get("id") or "").strip()
        if not workflow_id:
            raise RuntimeError("Existing n8n workflow had no id.")
        response, result = api_file_request("PUT", f"/workflows/{workflow_id}", remote_file, expected_sha256)
    else:
        response, result = api_file_request("POST", "/workflows", remote_file, expected_sha256)
    if activate:
        workflow_id = str(response.get("id") or "").strip()
        if not workflow_id:
            raise RuntimeError("n8n did not return a workflow id.")
        response, result = api_request("POST", f"/workflows/{workflow_id}/activate")
    return response, result


def preflight() -> dict[str, Any]:
    settings = config()
    script = f"""set -euo pipefail
key_file={shell_quote(settings['key_file'])}
curl --fail --silent --show-error --max-time 10 {shell_quote(settings['base_url'] + '/healthz')}
if [[ -r "$key_file" ]]; then echo api-key-present; else echo api-key-absent; exit 3; fi
"""
    result = execute_remote(script)
    return {"tool_id": TOOL_ID, "operation": "preflight", "result": result, "ok": result["ok"]}


def run_live_file_test() -> tuple[dict[str, Any], dict[str, Any]]:
    script = """set -euo pipefail
curl --fail-with-body --silent --show-error --max-time 60 -X POST http://127.0.0.1:5678/webhook/n8n-live-file-test >/dev/null
file_size="$(docker compose -f /home/chris/projects/cs-ai-lab-infra/compose.yaml exec -T n8n sh -lc 'test -s /home/node/.n8n-files/n8n-live-test.txt && wc -c < /home/node/.n8n-files/n8n-live-test.txt')"
file_sha256="$(docker compose -f /home/chris/projects/cs-ai-lab-infra/compose.yaml exec -T n8n sh -lc 'sha256sum /home/node/.n8n-files/n8n-live-test.txt | head -c 64')"
printf '{"file_size_bytes":%s,"file_sha256":"%s"}\\n' "$file_size" "$file_sha256"
"""
    result = execute_remote(script)
    return result_json(result), result


def append_log(command: str, approved: bool, payload: dict[str, Any]) -> None:
    result = payload.get("result", {})
    entry = {
        "logged_at": now(), "tool_id": TOOL_ID, "command": command, "approved": approved,
        "started_at": result.get("started_at"), "finished_at": result.get("finished_at"),
        "duration_ms": result.get("duration_ms"), "exit_code": result.get("exit_code"), "ok": payload.get("ok", result.get("ok")),
        "stdout_bytes": len(result.get("stdout", "")), "stderr_bytes": len(result.get("stderr", "")),
        "stdout_sha256": sha256(result.get("stdout", "")), "stderr_sha256": sha256(result.get("stderr", "")),
    }
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, separators=(",", ":")) + "\n")


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description="Governed n8n adapter for the T480 lab.")
    command_parser.add_argument("command", choices=["describe-requirements", "preflight", "list-workflows", "upsert-workflow", "activate-workflow", "deactivate-workflow", "get-execution", "run-live-file-test"])
    command_parser.add_argument("--workflow-file")
    command_parser.add_argument("--workflow-id")
    command_parser.add_argument("--activate", action="store_true")
    command_parser.add_argument("--approve", action="store_true")
    return command_parser


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    mutating = args.command in {"upsert-workflow", "activate-workflow", "deactivate-workflow", "run-live-file-test"}
    if mutating and not args.approve:
        raise PermissionError(f"{args.command} requires --approve after explicit operator approval.")
    if args.command == "describe-requirements":
        payload: dict[str, Any] = {
            "tool_id": TOOL_ID,
            "source": "Autonomous-Framework operational n8n adapter at 174226df8bec1407d8e4b2aab48f184005d436bf",
            "requirements": ["M2 n8n service running on T480", "T480-local n8n API key file", "T16-to-T480 preflight passing"],
            "mutating_commands": ["upsert-workflow", "activate-workflow", "deactivate-workflow", "run-live-file-test"],
        }
    elif args.command == "preflight":
        payload = preflight()
    elif args.command == "list-workflows":
        workflows, result = list_workflows()
        payload = {"tool_id": TOOL_ID, "workflows": workflows, "result": result, "ok": True}
    elif args.command == "get-execution":
        if not args.workflow_id:
            raise SystemExit("--workflow-id is required for get-execution")
        response, result = api_request("GET", f"/executions/{args.workflow_id}")
        payload = {"tool_id": TOOL_ID, "execution": response, "result": result, "ok": True}
    elif args.command == "activate-workflow":
        if not args.workflow_id:
            raise SystemExit("--workflow-id is required for activate-workflow")
        response, result = api_request("POST", f"/workflows/{args.workflow_id}/activate")
        payload = {"tool_id": TOOL_ID, "workflow": response, "result": result, "ok": True}
    elif args.command == "deactivate-workflow":
        if not args.workflow_id:
            raise SystemExit("--workflow-id is required for deactivate-workflow")
        response, result = api_request("POST", f"/workflows/{args.workflow_id}/deactivate")
        payload = {"tool_id": TOOL_ID, "workflow": response, "result": result, "ok": True}
    elif args.command == "run-live-file-test":
        response, result = run_live_file_test()
        payload = {"tool_id": TOOL_ID, "file_test": response, "result": result, "ok": True}
    else:
        if not args.workflow_file:
            raise SystemExit("--workflow-file is required for upsert-workflow")
        response, result = upsert_workflow(args.workflow_file, args.activate)
        payload = {"tool_id": TOOL_ID, "workflow": response, "result": result, "ok": True}
    append_log(args.command, args.approve, payload)
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("ok", True) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PermissionError, RuntimeError, ValueError) as error:
        print(json.dumps({"tool_id": TOOL_ID, "ok": False, "error": str(error)}, indent=2), file=sys.stderr)
        raise SystemExit(2)
