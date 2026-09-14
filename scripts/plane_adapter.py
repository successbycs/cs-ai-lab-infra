#!/usr/bin/env python3
"""Bounded T16 Plane-access adapter shared by application repositories.

This adapter verifies a private Plane web origin and lists project metadata.
It deliberately has no generic HTTP path, project/task mutation, evidence,
broker, or task-execution feature. Applications own their own Plane board
schema and tokens; this adapter only reads a referenced protected token file.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG = ROOT / "plane" / "plane-access.local.env"
_KEYS = frozenset({"PLANE_ORIGIN", "PLANE_WORKSPACE_SLUG", "PLANE_API_KEY_FILE", "PLANE_API_KEY_VARIABLE"})
_ORIGIN = re.compile(r"https?://[^/]+(?::[0-9]{1,5})?\Z")
_VARIABLE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")


class PlaneAccessError(RuntimeError):
    pass


def _private_file(path: Path, *, label: str) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        raise PlaneAccessError(f"{label} is missing") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise PlaneAccessError(f"{label} must be a regular file")
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise PlaneAccessError(f"{label} must be owned by this user with mode 0600")


def _parse_env(path: Path, *, allowed: frozenset[str], label: str) -> dict[str, str]:
    _private_file(path, label=label)
    values: dict[str, str] = {}
    try:
        rows = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PlaneAccessError(f"{label} cannot be read") from exc
    for row in rows:
        if not row or row.startswith("#"):
            continue
        key, separator, value = row.partition("=")
        if not separator or key not in allowed or key in values or not value.strip():
            raise PlaneAccessError(f"{label} has unsupported settings")
        values[key] = value.strip()
    if set(values) != allowed:
        raise PlaneAccessError(f"{label} must contain exactly its fixed settings")
    return values


def load_config(path: Path = LOCAL_CONFIG) -> dict[str, str]:
    values = _parse_env(path, allowed=_KEYS, label="Plane access configuration")
    if (not _ORIGIN.fullmatch(values["PLANE_ORIGIN"]) or not _VARIABLE.fullmatch(values["PLANE_API_KEY_VARIABLE"])
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", values["PLANE_WORKSPACE_SLUG"])):
        raise PlaneAccessError("Plane access configuration contains unsafe values")
    key_file = Path(values["PLANE_API_KEY_FILE"])
    if not key_file.is_absolute():
        raise PlaneAccessError("Plane token file path must be absolute")
    values["PLANE_API_KEY_FILE"] = str(key_file)
    return values


def load_token(settings: dict[str, str]) -> str:
    token_file = Path(settings["PLANE_API_KEY_FILE"])
    _private_file(token_file, label="Plane token file")
    variable = settings["PLANE_API_KEY_VARIABLE"]
    for row in token_file.read_text(encoding="utf-8").splitlines():
        key, separator, value = row.partition("=")
        if separator and key == variable and value.strip():
            return value.strip()
    raise PlaneAccessError("Plane token file does not contain the configured token variable")


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _powershell_json(script: str) -> dict[str, Any]:
    try:
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], check=False, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PlaneAccessError("Windows PowerShell Plane access is unavailable") from exc
    if result.returncode:
        raise PlaneAccessError("Windows PowerShell Plane request failed")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PlaneAccessError("Windows PowerShell Plane response was invalid") from exc
    if not isinstance(payload, dict):
        raise PlaneAccessError("Windows PowerShell Plane response was invalid")
    return payload


def _windows_wsl_path(path: str) -> str:
    return r"\\wsl.localhost\Ubuntu" + path.replace("/", "\\")


def web_status(settings: dict[str, str]) -> dict[str, Any]:
    origin = settings["PLANE_ORIGIN"]
    payload = _powershell_json("$ErrorActionPreference='Stop'; $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 " + _ps_quote(origin + "/") + "; @{http_status=[int]$r.StatusCode}|ConvertTo-Json -Compress")
    if payload.get("http_status") != 200:
        raise PlaneAccessError("Plane web origin returned an unexpected status")
    return {"status": "PASS", "origin": origin, "http_status": 200}


def list_projects(settings: dict[str, str]) -> dict[str, Any]:
    token_path, variable = _windows_wsl_path(settings["PLANE_API_KEY_FILE"]), settings["PLANE_API_KEY_VARIABLE"]
    url = settings["PLANE_ORIGIN"] + "/api/v1/workspaces/" + settings["PLANE_WORKSPACE_SLUG"] + "/projects/?per_page=100"
    script = "$ErrorActionPreference='Stop'; $line=Get-Content -LiteralPath " + _ps_quote(token_path) + " | Where-Object { $_ -like " + _ps_quote(variable + "=*") + " } | Select-Object -First 1; if (-not $line) { throw 'Plane token missing' }; $token=$line.Substring(" + str(len(variable) + 1) + "); (Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 -Headers @{'X-API-Key'=$token;'Accept'='application/json'} " + _ps_quote(url) + ").Content"
    payload = _powershell_json(script)
    records = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(records, list) or not all(isinstance(item, dict) and isinstance(item.get("name"), str) and isinstance(item.get("identifier"), str) for item in records):
        raise PlaneAccessError("Plane projects response has unexpected shape")
    projects = [{"name": item["name"], "identifier": item["identifier"]} for item in records]
    return {"status": "PASS", "workspace": settings["PLANE_WORKSPACE_SLUG"], "projects": sorted(projects, key=lambda item: (item["identifier"], item["name"])), "count": len(records)}


def open_browser(settings: dict[str, str]) -> dict[str, Any]:
    if os.name != "nt" and not shutil_which("powershell.exe"):
        raise PlaneAccessError("Windows PowerShell is required to open the T16 browser")
    command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "Start-Process " + _ps_quote(settings["PLANE_ORIGIN"] + "/")]
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise PlaneAccessError("Could not open Plane in the T16 browser")
    return {"status": "OPENED", "origin": settings["PLANE_ORIGIN"]}


def shutil_which(command: str) -> str | None:
    from shutil import which
    return which(command)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("web-status", "list-projects", "open-browser"))
    parser.add_argument("--approve", action="store_true", help="required only to open the local browser")
    args = parser.parse_args(argv)
    try:
        if args.operation == "open-browser" and not args.approve:
            raise PlaneAccessError("open-browser requires --approve")
        settings = load_config()
        if args.operation == "web-status": result = web_status(settings)
        elif args.operation == "list-projects": result = list_projects(settings)
        else:
            result = open_browser(settings)
        print(json.dumps(result, sort_keys=True)); return 0
    except PlaneAccessError as exc:
        print(f"CS_AI_LAB_PLANE_ACCESS_REFUSED: {exc}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
