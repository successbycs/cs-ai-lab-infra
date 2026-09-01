#!/usr/bin/env python3
"""Render the redacted PostgreSQL health snapshot as a static LAN dashboard."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

VALID_STATUSES = {"PASS", "WARN", "FAIL", "SKIP"}


def text(value: object) -> str:
    return html.escape(str(value or "—"))


def status(value: object) -> str:
    value = str(value or "FAIL").upper()
    return value if value in VALID_STATUSES else "FAIL"


def badge(value: object) -> str:
    current = status(value)
    return f'<span class="status {current.lower()}">{current}</span>'


def render(payload: dict[str, Any]) -> str:
    runs = payload.get("runs") if isinstance(payload.get("runs"), list) else []
    latest = runs[0] if runs else None
    latest_checks = latest.get("checks", []) if isinstance(latest, dict) else []
    summary = (
        f"{badge(latest.get('overall_status'))} Latest result recorded {text(latest.get('recorded_at_nz'))}"
        if isinstance(latest, dict)
        else '<span class="status skip">NO DATA</span> Run <code>Healthcheck</code> from the T16 to publish the first result.'
    )
    check_rows = "".join(
        "<tr>"
        f"<td>{text(check.get('key'))}</td>"
        f"<td>{badge(check.get('status'))}</td>"
        f"<td>{text(check.get('detail'))}</td>"
        f"<td>{text(check.get('recommended_action'))}</td>"
        f"<td>{text(check.get('duration_ms'))}</td>"
        f"<td>{text(check.get('observed_started_at_nz'))}</td>"
        f"<td>{text(check.get('restart_count'))}</td>"
        "</tr>"
        for check in latest_checks
        if isinstance(check, dict)
    ) or '<tr><td colspan="7">No individual check results are available.</td></tr>'
    history_rows = "".join(
        "<tr>"
        f"<td>{text(run.get('run_id'))}</td>"
        f"<td>{text(run.get('recorded_at_nz'))}</td>"
        f"<td>{badge(run.get('overall_status'))}</td>"
        f"<td>{text(run.get('finished_at_nz'))}</td>"
        "</tr>"
        for run in runs
        if isinstance(run, dict)
    ) or '<tr><td colspan="4">No published health checks yet.</td></tr>'
    generated_at = text(payload.get("generated_at_nz"))
    return f"""<!doctype html>
<html lang="en-NZ">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="60">
  <title>CS AI Lab Health</title>
  <style>
    :root {{ color-scheme: dark; font-family: system-ui, sans-serif; background: #10151c; color: #edf2f7; }}
    body {{ margin: 0; padding: 28px; max-width: 1180px; margin-inline: auto; }}
    h1 {{ margin: 0; font-size: 1.65rem; }} h2 {{ margin-top: 32px; font-size: 1.1rem; }}
    .meta {{ color: #aab7c4; font-size: .9rem; }} .summary {{ margin: 18px 0; font-size: 1.05rem; }}
    table {{ width: 100%; border-collapse: collapse; background: #17212b; overflow: hidden; border-radius: 8px; }}
    th, td {{ padding: 11px 12px; text-align: left; border-bottom: 1px solid #2b3947; vertical-align: top; }}
    th {{ color: #b7c6d5; font-size: .82rem; text-transform: uppercase; letter-spacing: .04em; }}
    .status {{ display: inline-block; min-width: 48px; padding: 3px 7px; border-radius: 999px; font-size: .76rem; font-weight: 700; text-align: center; }}
    .pass {{ background: #164c35; color: #a7f3c2; }} .warn {{ background: #594315; color: #fde68a; }}
    .fail {{ background: #5b252b; color: #fecaca; }} .skip {{ background: #354150; color: #d0d9e3; }}
    code {{ color: #b8e5ff; }}
  </style>
</head>
<body>
  <h1>CS AI Lab Health</h1>
  <p class="meta">Private LAN status page · auto-refreshes every 60 seconds · generated {generated_at}</p>
  <p class="summary">{summary}</p>
  <h2>Latest checks</h2>
  <table><thead><tr><th>Check</th><th>Status</th><th>Detail</th><th>Recommended action</th><th>Duration (ms)</th><th>Started (NZ)</th><th>Restarts</th></tr></thead><tbody>{check_rows}</tbody></table>
  <h2>Recent Healthchecks</h2>
  <table><thead><tr><th>Run</th><th>Recorded (NZ)</th><th>Result</th><th>Finished (NZ)</th></tr></thead><tbody>{history_rows}</tbody></table>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the health dashboard from redacted PostgreSQL JSON.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.load(__import__("sys").stdin)
    if not isinstance(payload, dict):
        raise SystemExit("Dashboard payload must be a JSON object.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(render(payload), encoding="utf-8")
    temporary.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
