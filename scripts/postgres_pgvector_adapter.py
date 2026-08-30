#!/usr/bin/env python3
"""Governed PostgreSQL + pgvector adapter for the private T480 lab.

It applies the AF Supabase adapter's capability and approval model to the
local Docker PostgreSQL service. It does not expose a database port, accept
raw SQL, or move the database password off the T480.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
from typing import Any

try:
    from scripts.t480_adapter import configured_target, run_command, ssh_command, wsl_bash_script_command
except ModuleNotFoundError:  # pragma: no cover
    from t480_adapter import configured_target, run_command, ssh_command, wsl_bash_script_command

ROOT = Path(__file__).resolve().parent.parent
REMOTE_ROOT = "/home/chris/projects/cs-ai-lab-infra"
MIGRATIONS_ROOT = ROOT / "postgres" / "migrations"
FOREX_ROOT = ROOT.parent / "forex"
REMOTE_FOREX_ROOT = "/home/chris/projects/forex"
FOREX_M2_MIGRATION = "sql/migrations/001_m2_historical_data.sql"
FOREX_M2_IMPORTER = "scripts/build_m2_postgres_import.py"
LOG_PATH = ROOT / ".postgres-pgvector-execution.local.jsonl"
TOOL_ID = "postgres_pgvector_t480"
MIGRATION_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.sql\Z")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def remote_script(body: str) -> dict[str, Any]:
    script = f"""set -euo pipefail
cd {REMOTE_ROOT}
if [[ ! -f .env ]]; then
  printf 'T480 lab .env is missing. Complete M2 deployment first.\\n' >&2
  exit 3
fi
set -a
source .env
set +a
{body}
"""
    return run_command(ssh_command(configured_target(), wsl_bash_script_command(script)))


def preflight() -> dict[str, Any]:
    result = remote_script("""docker compose ps postgres
docker compose exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" </dev/null
""")
    return {"tool_id": TOOL_ID, "operation": "preflight", "result": result, "ok": result["ok"]}


def inspect() -> dict[str, Any]:
    result = remote_script("""docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc \
  "SELECT current_database(), current_user, extname FROM pg_extension WHERE extname = 'vector';" </dev/null
""")
    return {"tool_id": TOOL_ID, "operation": "inspect", "result": result, "ok": result["ok"]}


def vector_probe() -> dict[str, Any]:
    result = remote_script("""docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc \
  "SELECT '[1,0,0]'::vector <-> '[0,1,0]'::vector AS l2_distance;" </dev/null
""")
    return {"tool_id": TOOL_ID, "operation": "vector_probe", "result": result, "ok": result["ok"]}


def resolve_migration(value: str) -> str:
    name = Path(value).name
    if name != value or not MIGRATION_NAME.fullmatch(name):
        raise ValueError("Migration must be a single .sql filename inside postgres/migrations.")
    local_path = MIGRATIONS_ROOT / name
    if not local_path.is_file():
        raise ValueError(f"Reviewed migration does not exist: postgres/migrations/{name}")
    return name


def apply_migration(filename: str) -> dict[str, Any]:
    safe_name = resolve_migration(filename)
    expected_sha256 = hashlib.sha256((MIGRATIONS_ROOT / safe_name).read_bytes()).hexdigest()
    result = remote_script(f"""migration_file="postgres/migrations/{safe_name}"
[[ -f "$migration_file" ]] || {{ printf 'Migration is absent on T480: %s\\n' "$migration_file" >&2; exit 4; }}
expected_sha256="{expected_sha256}"
actual_sha256="$(sha256sum "$migration_file" | head -c 64)"
[[ "$actual_sha256" == "$expected_sha256" ]] || {{ printf 'Migration hash differs from reviewed T16 file.\\n' >&2; exit 5; }}
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$migration_file"
""")
    return {"tool_id": TOOL_ID, "operation": "apply_migration", "migration": safe_name, "result": result, "ok": result["ok"]}


def _forex_m2_asset(relative_path: str) -> tuple[Path, str]:
    """Return one of the two fixed Forex M2 assets and its SHA-256 digest."""
    if relative_path not in {FOREX_M2_MIGRATION, FOREX_M2_IMPORTER}:
        raise ValueError("unknown fixed Forex M2 asset")
    path = FOREX_ROOT / relative_path
    if not path.is_file():
        raise ValueError(f"required Forex M2 asset is absent: {relative_path}")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def apply_forex_m2_schema() -> dict[str, Any]:
    _, expected_sha256 = _forex_m2_asset(FOREX_M2_MIGRATION)
    result = remote_script(f"""asset="{REMOTE_FOREX_ROOT}/{FOREX_M2_MIGRATION}"
[[ -f "$asset" ]] || {{ printf 'Forex M2 migration is absent on T480.\\n' >&2; exit 4; }}
expected_sha256="{expected_sha256}"
actual_sha256="$(sha256sum "$asset" | head -c 64)"
[[ "$actual_sha256" == "$expected_sha256" ]] || {{ printf 'Forex M2 migration hash differs from the reviewed controller file.\\n' >&2; exit 5; }}
already_applied="$(docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT to_regclass('forex.source_registry') IS NOT NULL;" </dev/null)"
if [[ "$already_applied" == "t" ]]; then
  printf 'FOREX_M2_SCHEMA_ALREADY_APPLIED sha256:%s\\n' "$actual_sha256"
  exit 0
fi
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$asset"
printf 'FOREX_M2_SCHEMA_APPLIED sha256:%s\\n' "$actual_sha256"
""")
    return {"tool_id": TOOL_ID, "operation": "forex_m2_apply_schema", "asset_sha256": f"sha256:{expected_sha256}", "result": result, "ok": result["ok"]}


def import_forex_m2_snapshot() -> dict[str, Any]:
    _, expected_sha256 = _forex_m2_asset(FOREX_M2_IMPORTER)
    result = remote_script(f"""asset="{REMOTE_FOREX_ROOT}/{FOREX_M2_IMPORTER}"
[[ -f "$asset" ]] || {{ printf 'Forex M2 importer is absent on T480.\\n' >&2; exit 4; }}
expected_sha256="{expected_sha256}"
actual_sha256="$(sha256sum "$asset" | head -c 64)"
[[ "$actual_sha256" == "$expected_sha256" ]] || {{ printf 'Forex M2 importer hash differs from the reviewed controller file.\\n' >&2; exit 5; }}
cd "{REMOTE_FOREX_ROOT}"
python3 "$asset" | docker compose -f "{ROOT / 'compose.yaml'}" exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"
printf 'FOREX_M2_IMPORT_EXECUTED sha256:%s\\n' "$actual_sha256"
""")
    return {"tool_id": TOOL_ID, "operation": "forex_m2_import_snapshot", "asset_sha256": f"sha256:{expected_sha256}", "result": result, "ok": result["ok"]}


def verify_forex_m2_snapshot() -> dict[str, Any]:
    result = remote_script("""docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc \
"SELECT 'FOREX_M2_POSTGRES_VERIFY_OK',
 (SELECT count(*) FROM forex.source_registry),
 (SELECT count(*) FROM forex.raw_observation),
 (SELECT count(*) FROM forex.dataset_snapshot),
 (SELECT count(*) FROM forex.price_bar),
 (SELECT artifact_sha256 FROM forex.dataset_snapshot WHERE snapshot_id = 'm2-m1-eurusd-h1-720'),
 (SELECT payload_sha256 FROM forex.raw_observation WHERE observation_id = 'm1-demo-eurusd-h1-720');" </dev/null
""")
    return {"tool_id": TOOL_ID, "operation": "forex_m2_verify_snapshot", "result": result, "ok": result["ok"]}


def append_log(command: str, approved: bool, payload: dict[str, Any]) -> None:
    result = payload.get("result", {})
    entry = {
        "logged_at": now(), "tool_id": TOOL_ID, "command": command, "approved": approved,
        "started_at": result.get("started_at"), "finished_at": result.get("finished_at"),
        "duration_ms": result.get("duration_ms"), "exit_code": result.get("exit_code"), "ok": payload.get("ok"),
        "stdout_bytes": len(result.get("stdout", "")), "stderr_bytes": len(result.get("stderr", "")),
        "stdout_sha256": sha256(result.get("stdout", "")), "stderr_sha256": sha256(result.get("stderr", "")),
    }
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, separators=(",", ":")) + "\n")


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description="Governed T480 PostgreSQL + pgvector adapter.")
    command_parser.add_argument("command", choices=["describe-requirements", "preflight", "inspect", "vector-probe", "apply-migration", "forex-m2-apply-schema", "forex-m2-import", "forex-m2-verify"])
    command_parser.add_argument("--migration-file")
    command_parser.add_argument("--approve", action="store_true")
    return command_parser


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command in {"apply-migration", "forex-m2-apply-schema", "forex-m2-import"} and not args.approve:
        raise PermissionError(f"{args.command} requires --approve after explicit operator approval.")
    if args.command == "describe-requirements":
        payload: dict[str, Any] = {
            "tool_id": TOOL_ID,
            "source": "AF Supabase adapter capability and approval model, adapted for local PostgreSQL",
            "requirements": ["M2 PostgreSQL service running", "T480-local .env", "reviewed SQL file in postgres/migrations"],
            "read_only_commands": ["preflight", "inspect", "vector-probe"],
            "mutating_commands": ["apply-migration", "forex-m2-apply-schema", "forex-m2-import"],
        }
    elif args.command == "preflight":
        payload = preflight()
    elif args.command == "inspect":
        payload = inspect()
    elif args.command == "vector-probe":
        payload = vector_probe()
    elif args.command == "forex-m2-apply-schema":
        payload = apply_forex_m2_schema()
    elif args.command == "forex-m2-import":
        payload = import_forex_m2_snapshot()
    elif args.command == "forex-m2-verify":
        payload = verify_forex_m2_snapshot()
    else:
        if not args.migration_file:
            raise SystemExit("--migration-file is required for apply-migration")
        payload = apply_migration(args.migration_file)
    append_log(args.command, args.approve, payload)
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("ok", True) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PermissionError, RuntimeError, ValueError) as error:
        print(json.dumps({"tool_id": TOOL_ID, "ok": False, "error": str(error)}, indent=2), file=sys.stderr)
        raise SystemExit(2)
