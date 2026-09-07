#!/usr/bin/env python3
"""Create T16-local DPAPI recovery records from the local lab .env file."""

from __future__ import annotations

import argparse
import base64
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.t16_backup_pull import backup_target, require_prepared_target, run_command, windows_path
    from scripts.t480_adapter import configured_target, ssh_command, wsl_bash_script_command
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from t16_backup_pull import backup_target, require_prepared_target, run_command, windows_path
    from t480_adapter import configured_target, ssh_command, wsl_bash_script_command

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
POLICY_PATH = ROOT / ".w1-recovery.local"
ENV_RECORD_ID = "t16-dpapi-cs-ai-lab-env-v1"
KEY_RECORD_ID = "t16-dpapi-cs-ai-lab-n8n-key-v1"


def local_environment_bytes() -> bytes:
    if not ENV_PATH.is_file():
        raise RuntimeError("Local .env is missing; no recovery record was created.")
    return ENV_PATH.read_bytes()


def powershell_record_script(target_windows: str) -> str:
    """Build a script that keeps incoming secret material inside PowerShell."""
    return f'''$ErrorActionPreference = 'Stop'
$target = '{target_windows.replace("'", "''")}'
$environmentText = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($environmentText)) {{ throw 'Environment input is empty.' }}
$keyMatch = [regex]::Match($environmentText, '(?m)^N8N_ENCRYPTION_KEY=([^\\r\\n]+)$')
if (!$keyMatch.Success) {{ throw 'N8N_ENCRYPTION_KEY is absent from the local environment file.' }}
$recordRoot = Join-Path $target 'recovery-records'
New-Item -ItemType Directory -Force -Path $recordRoot | Out-Null
& icacls.exe $recordRoot /inheritance:r /grant:r "$env:USERNAME`:(OI)(CI)F" /grant:r "SYSTEM`:(OI)(CI)F" | Out-Null
function Protect-Record([string]$name, [string]$value) {{
  $secure = ConvertTo-SecureString -String $value -AsPlainText -Force
  $protected = ConvertFrom-SecureString -SecureString $secure
  $path = Join-Path $recordRoot $name
  [IO.File]::WriteAllText($path, $protected, [Text.Encoding]::ASCII)
  $roundTrip = [System.Net.NetworkCredential]::new('recovery', (Get-Content -LiteralPath $path -Raw | ConvertTo-SecureString)).Password
  if ($roundTrip -cne $value) {{ throw "DPAPI round-trip failed for $name" }}
  return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}}
$environmentHash = Protect-Record 'environment.v1.dpapi' $environmentText
$keyHash = Protect-Record 'n8n-encryption-key.v1.dpapi' $keyMatch.Groups[1].Value
[pscustomobject]@{{ environment_record_id = '{ENV_RECORD_ID}'; n8n_key_record_id = '{KEY_RECORD_ID}'; protection = 'CurrentUser-DPAPI'; environment_record_sha256 = $environmentHash; n8n_key_record_sha256 = $keyHash }} | ConvertTo-Json -Compress'''


def mark_records_confirmed() -> None:
    if not POLICY_PATH.is_file():
        raise RuntimeError(".w1-recovery.local is missing; recovery policy must be configured first.")
    lines = POLICY_PATH.read_text(encoding="utf-8").splitlines()
    values = {line.partition("=")[0]: line.partition("=")[2] for line in lines if "=" in line}
    required_policy = ("W1_RPO_HOURS", "W1_RTO_HOURS", "W1_T16_RETENTION_DAILY", "W1_OLLAMA_MODEL_DISPOSITION")
    missing = [key for key in required_policy if not values.get(key)]
    if missing:
        raise RuntimeError("Recovery policy is incomplete: " + ", ".join(missing))
    replacements = {
        "W1_ENVIRONMENT_RECOVERY_RECORD_ID": ENV_RECORD_ID,
        "W1_N8N_ENCRYPTION_KEY_RECOVERY_RECORD_ID": KEY_RECORD_ID,
        "W1_RECOVERY_RECORDS_CONFIRMED": "yes",
    }
    updated = [
        f"{key}={replacements[key]}" if key in replacements else line
        for line in lines
        for key in [line.partition("=")[0]]
    ]
    temporary = POLICY_PATH.with_suffix(".local.tmp")
    temporary.write_text("\n".join(updated) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(POLICY_PATH)


def remote_environment_command() -> list[str]:
    script = """set -euo pipefail
cd /home/chris/projects/cs-ai-lab-infra
[[ -f .env ]] || { printf 'T480 .env is missing.\\n' >&2; exit 3; }
cat .env
"""
    return ssh_command(configured_target(), wsl_bash_script_command(script))


def create_records(*, from_t480: bool) -> dict[str, Any]:
    target = backup_target()
    require_prepared_target(target)
    target_windows = windows_path(target)
    encoded = base64.b64encode(powershell_record_script(target_windows).encode("utf-16-le")).decode("ascii")
    producer_returncode = 0
    producer_stderr = ""
    try:
        if from_t480:
            # Keep the remote environment out of command arguments, files, and
            # tool output.  Capturing it in this short-lived process avoids the
            # inherited-pipe deadlock that can otherwise prevent PowerShell from
            # seeing end-of-file on its standard input.
            producer = subprocess.run(
                remote_environment_command(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=45,
            )
            producer_returncode = producer.returncode
            producer_stderr = producer.stderr.decode("utf-8", errors="replace")[:500]
            if producer_returncode != 0:
                return {
                    "ok": False,
                    "producer_exit_code": producer_returncode,
                    "producer_stderr": producer_stderr,
                    "consumer_exit_code": "not-started",
                }
            environment = bytearray(producer.stdout)
        else:
            environment = bytearray(local_environment_bytes())
    except subprocess.TimeoutExpired:
        return {"ok": False, "producer_exit_code": 124, "producer_stderr": "timed out", "consumer_exit_code": "not-started"}

    consumer = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        consumer_stdout, consumer_stderr = consumer.communicate(input=environment, timeout=45)
    except subprocess.TimeoutExpired:
        consumer.kill()
        consumer.communicate()
        return {"ok": False, "producer_exit_code": producer_returncode, "producer_stderr": producer_stderr, "consumer_exit_code": 124}
    finally:
        for index in range(len(environment)):
            environment[index] = 0
    if producer_returncode != 0 or consumer.returncode != 0:
        return {"ok": False, "producer_exit_code": producer_returncode, "producer_stderr": producer_stderr[:500], "consumer_exit_code": consumer.returncode}
    mark_records_confirmed()
    return {"ok": True}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--from-t480", action="store_true", help="Stream the deployed T480 .env through the governed strict-host-key connection.")
    args = parser.parse_args(argv)
    if not args.approve:
        raise PermissionError("DPAPI recovery-record creation requires --approve.")
    outcome = create_records(from_t480=args.from_t480)
    if not outcome["ok"]:
        producer_code = outcome.get("producer_exit_code", "not-started")
        consumer_code = outcome.get("consumer_exit_code", "not-started")
        print(
            f"DPAPI recovery-record creation failed; local policy remains unchanged (T480 stream exit {producer_code}; DPAPI exit {consumer_code}).",
            file=sys.stderr,
        )
        return 1
    print("T16 DPAPI recovery records created and independently round-trip verified.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PermissionError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"DPAPI recovery-record creation refused: {error}", file=sys.stderr)
        raise SystemExit(2)
