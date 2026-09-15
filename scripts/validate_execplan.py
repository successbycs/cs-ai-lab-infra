#!/usr/bin/env python3
"""Fail when an active repository ExecPlan lacks its required living structure."""
from __future__ import annotations

import argparse
import re
from pathlib import Path


REQUIRED_HEADINGS = (
    "Purpose / Big Picture",
    "Progress",
    "Surprises & Discoveries",
    "Decision Log",
    "Outcomes & Retrospective",
    "Context and Orientation",
    "Plan of Work",
    "Concrete Steps",
    "Validation and Acceptance",
    "Idempotence and Recovery",
    "Artifacts and Notes",
)
SKIPPED_FILENAMES = {"README.md", "TEMPLATE.md"}
VALID_STATUSES = {"proposed", "active", "blocked", "complete"}
TIMESTAMPED_CHECKBOX = re.compile(r"^- \[[ x]\] \(\d{4}-\d{2}-\d{2} \d{2}:\d{2}Z\)", re.MULTILINE)


def plan_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(path for path in target.rglob("*.md") if path.name not in SKIPPED_FILENAMES)


def section(content: str, heading: str) -> str:
    marker = f"## {heading}\n"
    start = content.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    end = content.find("\n## ", start)
    return content[start:] if end < 0 else content[start:end]


def validation_errors(path: Path) -> list[str]:
    content = path.read_text(encoding="utf-8")
    errors = [
        f"missing heading: ## {heading}"
        for heading in REQUIRED_HEADINGS
        if f"## {heading}\n" not in content
    ]
    if "This ExecPlan is a living document." not in content:
        errors.append("missing living-document declaration")
    if "PLANS.md" not in content:
        errors.append("missing reference to PLANS.md")
    statuses = re.findall(r"^Status: ([a-z]+)$", content, flags=re.MULTILINE)
    if len(statuses) != 1 or statuses[0] not in VALID_STATUSES:
        errors.append("missing or invalid Status (use proposed, active, blocked, or complete)")
    if not TIMESTAMPED_CHECKBOX.search(section(content, "Progress")):
        errors.append("Progress must include a timestamped checkbox")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default="plans", type=Path)
    args = parser.parse_args()
    if not args.path.exists():
        print(f"ExecPlan path does not exist: {args.path}")
        return 2
    failures = 0
    for path in plan_files(args.path):
        errors = validation_errors(path)
        if errors:
            failures += 1
            for error in errors:
                print(f"{path}: {error}")
        else:
            print(f"EXECPLAN_VALID {path}")
    if failures:
        return 1
    print("EXECPLAN_CHECK_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
