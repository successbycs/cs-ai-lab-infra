#!/usr/bin/env python3
"""Configure non-secret Wave 1 recovery policy values on the T16.

It never reads .env or n8n data. Record confirmation remains unavailable from
this policy setup command; it is set only after the separate DPAPI-record
creation command independently round-trip verifies both protected records.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".w1-recovery.local"
RECORD_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,127}\Z")


def validate_positive(name: str, value: int) -> int:
    if value <= 0:
        raise ValueError(f"{name} must be positive.")
    return value


def configure(*, environment_record_id: str, key_record_id: str, rpo_hours: int, rto_hours: int, retention_daily: int, confirm_records: bool) -> None:
    if CONFIG_PATH.exists():
        raise RuntimeError(".w1-recovery.local already exists; do not overwrite an established recovery policy.")
    if not RECORD_ID.fullmatch(environment_record_id) or not RECORD_ID.fullmatch(key_record_id):
        raise ValueError("Recovery record IDs must be opaque 3-128 character identifiers.")
    rpo_hours = validate_positive("RPO hours", rpo_hours)
    rto_hours = validate_positive("RTO hours", rto_hours)
    retention_daily = validate_positive("T16 retention", retention_daily)
    value = (
        f"W1_ENVIRONMENT_RECOVERY_RECORD_ID={environment_record_id}\n"
        f"W1_N8N_ENCRYPTION_KEY_RECOVERY_RECORD_ID={key_record_id}\n"
        f"W1_RECOVERY_RECORDS_CONFIRMED={'yes' if confirm_records else 'no'}\n"
        f"W1_RPO_HOURS={rpo_hours}\n"
        f"W1_RTO_HOURS={rto_hours}\n"
        f"W1_T16_RETENTION_DAILY={retention_daily}\n"
        "W1_OLLAMA_MODEL_DISPOSITION=redownload-reviewed-models\n"
    )
    temporary = CONFIG_PATH.with_suffix(".local.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(CONFIG_PATH)


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description=__doc__)
    command_parser.add_argument("--environment-record-id", required=True)
    command_parser.add_argument("--n8n-key-record-id", required=True)
    command_parser.add_argument("--rpo-hours", type=int, default=24)
    command_parser.add_argument("--rto-hours", type=int, default=4)
    command_parser.add_argument("--retention-daily", type=int, default=30)
    command_parser.add_argument("--confirm-owner-records", action="store_true")
    command_parser.add_argument("--approve", action="store_true")
    return command_parser


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.approve:
        raise PermissionError("Configuration requires --approve after owner review.")
    configure(
        environment_record_id=args.environment_record_id,
        key_record_id=args.n8n_key_record_id,
        rpo_hours=args.rpo_hours,
        rto_hours=args.rto_hours,
        retention_daily=args.retention_daily,
        confirm_records=args.confirm_owner_records,
    )
    print("Wave 1 recovery policy configured locally; capture remains gated until records are confirmed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PermissionError, RuntimeError, ValueError) as error:
        print(f"Wave 1 recovery policy refused: {error}", file=sys.stderr)
        raise SystemExit(2)
