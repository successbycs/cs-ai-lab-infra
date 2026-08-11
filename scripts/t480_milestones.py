#!/usr/bin/env python3
"""Keep local, evidence-backed progress for the T480 lab milestones."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "t480" / "milestone-registry.json"
DEFAULT_STATE_PATH = ROOT / ".t480-milestones.local.json"
VALID_RESULTS = {"pass", "fail"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def registry() -> dict[str, Any]:
    data = load_json(REGISTRY_PATH, {})
    for milestone in data["milestones"]:
        if not any(check.get("real_world_execution") for check in milestone["checks"]):
            raise RuntimeError(f"{milestone['id']} must define a real_world_execution check.")
    return data


def milestones_by_id(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {milestone["id"]: milestone for milestone in data["milestones"]}


def state(path: Path) -> dict[str, Any]:
    data = load_json(path, {"version": 1, "milestones": {}})
    if "last_updated_at" not in data:
        timestamps: list[str] = []
        for milestone in data["milestones"].values():
            timestamps.extend(value for key, value in milestone.items() if key.endswith("_at") and isinstance(value, str))
            timestamps.extend(
                check["recorded_at"]
                for check in milestone.get("checks", {}).values()
                if isinstance(check.get("recorded_at"), str)
            )
        data["last_updated_at"] = max(timestamps, default=None)
    return data


def write_state(path: Path, data: dict[str, Any]) -> None:
    data["last_updated_at"] = now()
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def milestone_state(data: dict[str, Any], milestone_id: str) -> dict[str, Any]:
    return data["milestones"].setdefault(milestone_id, {"status": "planned", "checks": {}, "evidence": []})


def dependencies_proven(definitions: dict[str, dict[str, Any]], current_state: dict[str, Any], milestone: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for dependency in milestone["depends_on"]:
        if dependency not in definitions or current_state["milestones"].get(dependency, {}).get("status") != "proven":
            missing.append(dependency)
    return missing


def display_status(definitions: dict[str, dict[str, Any]], current_state: dict[str, Any], state_path: Path) -> dict[str, Any]:
    result: list[dict[str, Any]] = []
    for milestone_id, milestone in definitions.items():
        local = current_state["milestones"].get(milestone_id, {})
        check_results = local.get("checks", {})
        result.append(
            {
                "id": milestone_id,
                "name": milestone["name"],
                "status": local.get("status", "planned"),
                "dependencies": milestone["depends_on"],
                "checks_passed": sum(check_results.get(check["id"], {}).get("result") == "pass" for check in milestone["checks"]),
                "checks_required": len(milestone["checks"]),
                "blocked_by": dependencies_proven(definitions, current_state, milestone),
            }
        )
    return {
        "state_file": str(state_path),
        "last_updated_at": current_state.get("last_updated_at"),
        "milestones": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Record evidence-backed T480 lab milestone progress.")
    parser.add_argument("command", choices=["status", "show", "start", "record-check", "prove"])
    parser.add_argument("--id", help="Milestone ID, for example M0.")
    parser.add_argument("--check", help="Acceptance-check ID.")
    parser.add_argument("--result", choices=sorted(VALID_RESULTS), help="Check result.")
    parser.add_argument("--evidence", help="Concise local evidence reference or summary.")
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_PATH, help=argparse.SUPPRESS)
    args = parser.parse_args()

    definitions = milestones_by_id(registry())
    current_state = state(args.state_file)
    if args.command == "status":
        print(json.dumps(display_status(definitions, current_state, args.state_file), indent=2))
        return 0
    if not args.id or args.id not in definitions:
        raise SystemExit("A valid --id is required.")

    milestone = definitions[args.id]
    if args.command == "show":
        print(
            json.dumps(
                {
                    "id": args.id,
                    "name": milestone["name"],
                    "objective": milestone["objective"],
                    "status": current_state["milestones"].get(args.id, {}).get("status", "planned"),
                    "execution_steps": milestone.get("execution_steps", []),
                    "checks": milestone["checks"],
                },
                indent=2,
            )
        )
        return 0
    local = milestone_state(current_state, args.id)
    blocked_by = dependencies_proven(definitions, current_state, milestone)
    if blocked_by:
        raise SystemExit(f"{args.id} is blocked until proven: {', '.join(blocked_by)}")

    if args.command == "start":
        local["status"] = "in_progress"
        local["started_at"] = now()
    elif args.command == "record-check":
        check_ids = {check["id"] for check in milestone["checks"]}
        if not args.check or args.check not in check_ids or not args.result or not args.evidence:
            raise SystemExit("record-check requires valid --check, --result, and --evidence values.")
        local["status"] = "in_progress"
        local["checks"][args.check] = {"result": args.result, "evidence": args.evidence, "recorded_at": now()}
    else:
        missing = [check["id"] for check in milestone["checks"] if local["checks"].get(check["id"], {}).get("result") != "pass"]
        if missing:
            raise SystemExit(f"Cannot prove {args.id}; passing evidence is missing for: {', '.join(missing)}")
        local["status"] = "proven"
        local["proven_at"] = now()

    write_state(args.state_file, current_state)
    print(
        json.dumps(
            {
                "milestone": args.id,
                "status": local["status"],
                "updated_at": current_state["last_updated_at"],
                "state_file": str(args.state_file),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
