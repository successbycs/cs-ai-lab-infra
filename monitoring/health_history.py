"""Redacted controller-side Healthcheck history and weekly availability report."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

MAX_HISTORY_RECORDS = 2_000


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _states(summary: dict[str, Any]) -> dict[str, str]:
    values = {"overall": str(summary.get("overall_status", "FAIL"))}
    for check in summary.get("checks", []):
        if isinstance(check, dict) and isinstance(check.get("key"), str):
            values[check["key"]] = str(check.get("status", "FAIL"))
    return values


def append(
    summary: dict[str, Any],
    *,
    history_path: Path,
    latest_path: Path,
    transitions_path: Path,
) -> dict[str, int]:
    """Persist only normalized status data and transition-only events."""
    previous = _read_json(latest_path)
    record = dict(summary)
    record["recorded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    history_path.parent.mkdir(parents=True, exist_ok=True)
    existing = history_path.read_text(encoding="utf-8").splitlines() if history_path.exists() else []
    existing = [line for line in existing if line.strip()][-(MAX_HISTORY_RECORDS - 1) :]
    existing.append(json.dumps(record, separators=(",", ":")))
    temporary = history_path.with_suffix(history_path.suffix + ".tmp")
    temporary.write_text("\n".join(existing) + "\n", encoding="utf-8")
    os.replace(temporary, history_path)
    _write_json(latest_path, record)

    previous_states = _states(previous) if previous else {}
    current_states = _states(record)
    changed = {
        key: {"from": previous_states.get(key), "to": value}
        for key, value in current_states.items()
        if previous_states.get(key) != value
    }
    if changed:
        transitions_path.parent.mkdir(parents=True, exist_ok=True)
        with transitions_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"recorded_at": record["recorded_at"], "changes": changed}, separators=(",", ":")) + "\n")
    return {"history_records": len(existing), "state_transitions": len(changed)}


def weekly_report(history_path: Path, output_path: Path, now: datetime | None = None) -> dict[str, Any]:
    """Write a simple local availability summary from the last seven days."""
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=7)
    records: list[dict[str, Any]] = []
    if history_path.exists():
        for line in history_path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
                recorded_at = datetime.fromisoformat(record["recorded_at"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
            if recorded_at >= since and isinstance(record, dict):
                records.append(record)
    counts = {status: sum(record.get("overall_status") == status for record in records) for status in ("PASS", "WARN", "FAIL", "SKIP")}
    report = {
        "period_start_utc": since.isoformat(timespec="seconds"),
        "period_end_utc": now.isoformat(timespec="seconds"),
        "runs": len(records),
        "counts": counts,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "# CS AI Lab weekly Healthcheck report\n\n"
        f"Period (UTC): {report['period_start_utc']} to {report['period_end_utc']}\n\n"
        f"Runs: {report['runs']} · PASS: {counts['PASS']} · WARN: {counts['WARN']} · FAIL: {counts['FAIL']} · SKIP: {counts['SKIP']}\n",
        encoding="utf-8",
    )
    return report
