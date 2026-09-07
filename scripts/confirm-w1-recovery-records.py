#!/usr/bin/env python3
"""Record the owner’s independent confirmation of Wave 1 recovery records."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".w1-recovery.local"
REQUIRED = {"W1_ENVIRONMENT_RECOVERY_RECORD_ID", "W1_N8N_ENCRYPTION_KEY_RECOVERY_RECORD_ID"}


def confirm() -> None:
    if not CONFIG_PATH.is_file():
        raise RuntimeError(".w1-recovery.local is missing; configure the recovery policy first.")
    lines = CONFIG_PATH.read_text(encoding="utf-8").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    missing = sorted(key for key in REQUIRED if not values.get(key))
    if missing:
        raise RuntimeError("Cannot confirm missing recovery record IDs: " + ", ".join(missing))
    updated = ["W1_RECOVERY_RECORDS_CONFIRMED=yes" if line.startswith("W1_RECOVERY_RECORDS_CONFIRMED=") else line for line in lines]
    if not any(line.startswith("W1_RECOVERY_RECORDS_CONFIRMED=") for line in lines):
        updated.append("W1_RECOVERY_RECORDS_CONFIRMED=yes")
    temporary = CONFIG_PATH.with_suffix(".local.tmp")
    temporary.write_text("\n".join(updated) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(CONFIG_PATH)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-owner-records", action="store_true")
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args(argv)
    if not args.approve or not args.confirm_owner_records:
        raise PermissionError("Confirmation requires both --confirm-owner-records and --approve.")
    confirm()
    print("Wave 1 recovery records marked confirmed locally.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PermissionError, RuntimeError) as error:
        print(f"Wave 1 recovery record confirmation refused: {error}", file=sys.stderr)
        raise SystemExit(2)
