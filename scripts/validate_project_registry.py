#!/usr/bin/env python3
"""Small dependency-free validator for the tracked project-registry example."""
import json
import re
import sys
from pathlib import Path

REQUIRED = {"id", "owner", "repository", "revision_or_image", "service", "exposure", "secrets_file_reference", "storage_backup", "resource_estimate", "update", "rollback"}

def main(path: str) -> int:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if set(document) != {"schema_version", "projects"} or document.get("schema_version") != "cs-ai-lab.projects.v1": raise ValueError("unsupported registry shape or schema_version")
    if not isinstance(document["projects"], list): raise ValueError("projects must be a list")
    ids = set()
    for project in document.get("projects", []):
        missing = REQUIRED - project.keys()
        if missing or set(project) != REQUIRED: raise ValueError(f"{project.get('id', '<unknown>')}: project fields must exactly match the contract")
        if not all(isinstance(project[field], str) and project[field] for field in ("id", "owner", "repository", "revision_or_image", "secrets_file_reference", "update", "rollback")): raise ValueError("required text fields must be non-empty strings")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", project["id"]) or project["id"] in ids: raise ValueError("project id must be unique and portable")
        ids.add(project["id"])
        if project["exposure"] not in {"none", "loopback", "private-ingress", "external-hosted"}: raise ValueError("invalid exposure")
        if not project["secrets_file_reference"].startswith("/"): raise ValueError("secrets_file_reference must be an absolute protected path")
        if not isinstance(project["service"], dict) or not {"name", "health_url"} <= project["service"].keys() or not isinstance(project["service"]["name"], str) or not (isinstance(project["service"]["health_url"], str) or project["service"]["health_url"] is None): raise ValueError("service needs typed name and health_url")
        if not isinstance(project["storage_backup"], dict) or not {"persistent_state", "backup_plan"} <= project["storage_backup"].keys() or not all(isinstance(project["storage_backup"][field], str) for field in ("persistent_state", "backup_plan")): raise ValueError("storage_backup incomplete")
        if not isinstance(project["resource_estimate"], dict) or not {"cpu", "memory", "pids"} <= project["resource_estimate"].keys() or not all(isinstance(project["resource_estimate"][field], str) for field in ("cpu", "memory")): raise ValueError("resource_estimate incomplete")
        if isinstance(project["resource_estimate"]["pids"], bool) or not isinstance(project["resource_estimate"]["pids"], int) or project["resource_estimate"]["pids"] < 1: raise ValueError("pids must be a positive integer")
    print(f"valid projects={len(ids)}")
    return 0

if __name__ == "__main__":
    try: raise SystemExit(main(sys.argv[1] if len(sys.argv) == 2 else "projects/registry.example.json"))
    except (OSError, ValueError, json.JSONDecodeError) as error: print(f"invalid registry: {error}", file=sys.stderr); raise SystemExit(2)
