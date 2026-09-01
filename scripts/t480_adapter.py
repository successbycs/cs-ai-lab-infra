#!/usr/bin/env python3
"""Governed SSH/WSL adapter for the T480 AI Lab.

Only the operation identifiers in t480/command-catalog.json are executable.
This program intentionally provides no argument for a shell, PowerShell, or SSH
command. Approval is an operator-facing audit signal; it is not a substitute
for the human approval required by the operating process.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from t480_core import (
    Operation,
    append_execution_log as append_shared_execution_log,
    build_ssh_command,
    build_wsl_powershell_command,
    execute_operation,
    fingerprint_files,
    load_transport_settings,
    preflight as shared_preflight,
    resolve_ssh_target,
    validate_catalog,
)
from t480_core.core import run_command as run_shared_command
from monitoring.health_history import append as append_health_history
from monitoring.health_history import weekly_report

TOOL_ID = "t480_wsl_lab"
SSH_TARGET_ENV = "T480_SSH_TARGET"
LOCAL_CONFIG_PATH = PROJECT_ROOT / ".env.t480.local"
EXECUTION_LOG_PATH = PROJECT_ROOT / ".t480-execution.local.jsonl"
HEALTH_HISTORY_PATH = PROJECT_ROOT / ".t480-healthcheck.local.jsonl"
HEALTH_LATEST_PATH = PROJECT_ROOT / ".t480-healthcheck.latest.json"
HEALTH_TRANSITIONS_PATH = PROJECT_ROOT / ".t480-healthcheck.transitions.local.jsonl"
HEALTH_WEEKLY_REPORT_PATH = PROJECT_ROOT / ".t480-healthcheck.weekly-report.local.md"
TRANSPORT_CONFIG_PATH = PROJECT_ROOT / "t480" / "transport-config.json"
TRANSPORT_SETTINGS = load_transport_settings(TRANSPORT_CONFIG_PATH)
TRANSCRIBER_ROOT = "/home/chris/projects/mp4-to-transcript"
TRANSCRIBER_INCOMING = f"{TRANSCRIBER_ROOT}/incoming"
TRANSCRIBER_WINDOWS_STAGING = "C:/Users/chris/TranscriptionInbox"
TRANSCRIBER_WSL_STAGING = "/mnt/c/Users/chris/TranscriptionInbox"
TRANSCRIBER_WINDOWS_EXPORT = "C:/Users/chris/TranscriptionExports"
TRANSCRIBER_WSL_EXPORT = "/mnt/c/Users/chris/TranscriptionExports"
TRANSCRIBER_LOCAL_EXPORT = Path("/mnt/c/Users/chris/Videos/Transcripts")
FOREX_ROOT = Path("/home/chris/projects/forex")
FOREX_REMOTE_ROOT = "/home/chris/projects/forex"
FOREX_REPOSITORY = "https://github.com/successbycs/forex.git"
FOREX_REVISION = "093b8f380932aa0a923bb743dcc83198086643e4"
FOREX_M1_CAPTURE = FOREX_ROOT / "runs/evidence/M1/20260829T064204Z/capture.stdout.json"
FOREX_M1_CAPTURE_REMOTE = f"{FOREX_REMOTE_ROOT}/runs/evidence/M1/20260829T064204Z/capture.stdout.json"
FOREX_M1_CAPTURE_SHA256 = "d3a79f0017fcd51ebd5a918a6094b257be902ebe9933e216462ceef07e4e731b"
FOREX_WINDOWS_STAGING = "C:/Users/chris/ForexEvidence"
# The name is passed as a quoted data argument at every boundary; allow normal
# Windows Explorer duplicate suffixes such as "Lesson (1).mp4".
PORTABLE_MP4_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._()\-]*\.mp4", re.IGNORECASE)

DOCKER_INSTALL_SCRIPT = """set -euo pipefail
apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
printf 'Types: deb\\nURIs: https://download.docker.com/linux/ubuntu\\nSuites: %s\\nComponents: stable\\nArchitectures: %s\\nSigned-By: /etc/apt/keyrings/docker.asc\\n' "${UBUNTU_CODENAME:-$VERSION_CODENAME}" "$(dpkg --print-architecture)" > /etc/apt/sources.list.d/docker.sources
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
usermod -aG docker chris
"""

# The command text is private to this adapter. Callers choose an operation ID,
# never a command or arguments.
OPERATIONS: dict[str, dict[str, Any]] = {
    "health": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$os = Get-CimInstance Win32_OperatingSystem; "
            "$computer = Get-CimInstance Win32_ComputerSystem; "
            "[pscustomobject]@{ hostname = $env:COMPUTERNAME; os = $os.Caption; "
            "version = $os.Version; memory_gib = [math]::Round($computer.TotalPhysicalMemory / 1GB, 1) } "
            "| ConvertTo-Json -Compress"
        ),
    },
    "storage": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "Get-CimInstance Win32_LogicalDisk -Filter 'DriveType = 3' | "
            "Select-Object DeviceID, @{Name='size_gib'; Expression={[math]::Round($_.Size / 1GB, 1)}}, "
            "@{Name='free_gib'; Expression={[math]::Round($_.FreeSpace / 1GB, 1)}} | ConvertTo-Json -Compress"
        ),
    },
    "health_dashboard_firewall_status": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$rule = Get-NetFirewallRule -DisplayName 'CS AI Lab Health Dashboard' -ErrorAction SilentlyContinue; "
            "if ($null -eq $rule) { '{\"present\":false}' } else { "
            "$port = $rule | Get-NetFirewallPortFilter; "
            "[pscustomobject]@{ present = $true; enabled = $rule.Enabled.ToString(); direction = $rule.Direction.ToString(); action = $rule.Action.ToString(); profiles = $rule.Profile.ToString(); protocol = $port.Protocol.ToString(); local_port = $port.LocalPort } | ConvertTo-Json -Compress }"
        ),
    },
    "health_dashboard_firewall_enable": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$name = 'CS AI Lab Health Dashboard'; "
            "$existing = @(Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue); "
            "if ($existing.Count -gt 1) { throw 'Refusing firewall change: more than one dashboard rule exists.' }; "
            "if ($existing.Count -eq 1) { Set-NetFirewallRule -InputObject $existing[0] -Enabled True -Direction Inbound -Action Allow -Profile Private; Set-NetFirewallPortFilter -AssociatedNetFirewallRule $existing[0] -Protocol TCP -LocalPort 8080 } else { New-NetFirewallRule -DisplayName $name -Description 'Allows the status-only CS AI Lab health dashboard on trusted private networks.' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8080 -Profile Private | Out-Null }; "
            "$rule = Get-NetFirewallRule -DisplayName $name; $port = $rule | Get-NetFirewallPortFilter; "
            "[pscustomobject]@{ present = $true; enabled = $rule.Enabled.ToString(); direction = $rule.Direction.ToString(); action = $rule.Action.ToString(); profiles = $rule.Profile.ToString(); protocol = $port.Protocol.ToString(); local_port = $port.LocalPort } | ConvertTo-Json -Compress"
        ),
    },
    "windows_restart": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "shutdown.exe /r /t 10 /f /d p:4:1 /c 'Approved CS AI Lab operator reboot'; "
            "'{\"restart_scheduled\":true,\"delay_seconds\":10}'"
        ),
    },
    "power_policy_status": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$scheme = (powercfg /getactivescheme) -join ' '; "
            "$sleep = (powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE) -join '\n'; "
            "$hibernate = (powercfg /query SCHEME_CURRENT SUB_SLEEP HIBERNATEIDLE) -join '\n'; "
            "$lid = (powercfg /query SCHEME_CURRENT SUB_BUTTONS LIDACTION) -join '\n'; "
            "[pscustomobject]@{ active_scheme = $scheme; sleep = $sleep; hibernate = $hibernate; lid_action = $lid } | ConvertTo-Json -Compress"
        ),
    },
    "power_policy_ac_always_on": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "powercfg /change standby-timeout-ac 0; "
            "powercfg /change hibernate-timeout-ac 0; "
            "powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0; "
            "powercfg /setactive SCHEME_CURRENT; "
            "$scheme = (powercfg /getactivescheme) -join ' '; "
            "$sleep = (powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE) -join '\n'; "
            "$hibernate = (powercfg /query SCHEME_CURRENT SUB_SLEEP HIBERNATEIDLE) -join '\n'; "
            "$lid = (powercfg /query SCHEME_CURRENT SUB_BUTTONS LIDACTION) -join '\n'; "
            "[pscustomobject]@{ active_scheme = $scheme; sleep = $sleep; hibernate = $hibernate; lid_action = $lid } | ConvertTo-Json -Compress"
        ),
    },
    "m5_maintenance_preflight": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$os = Get-CimInstance Win32_OperatingSystem; "
            "$bios = Get-CimInstance Win32_BIOS; "
            "$battery = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | "
            "Select-Object BatteryStatus,EstimatedChargeRemaining; "
            "$updateSettings = Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\WindowsUpdate\\UX\\Settings' -ErrorAction SilentlyContinue; "
            "$rebootRequired = (Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\RebootPending') -or (Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired'); "
            "$bitlocker = try { Get-BitLockerVolume | Select-Object MountPoint,ProtectionStatus,VolumeStatus } catch { @([pscustomobject]@{ error = $_.Exception.Message }) }; "
            "$scheme = (powercfg /getactivescheme) -join ' '; "
            "$sleep = ((powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE) | Select-String 'Current AC Power Setting Index').ToString().Trim(); "
            "$hibernate = ((powercfg /query SCHEME_CURRENT SUB_SLEEP HIBERNATEIDLE) | Select-String 'Current AC Power Setting Index').ToString().Trim(); "
            "$wsl = (wsl.exe --list --verbose) -join '\n'; "
            "$lab = (wsl.exe -d Ubuntu -- bash -lc 'cd /home/chris/projects/cs-ai-lab-infra && docker compose ps; latest=$(ls -1t postgres/backup/*.sql.gz 2>/dev/null | head -n1 | xargs -r basename); printf ""latest_backup=%s\\n"" ""$latest""; curl --silent --show-error --max-time 10 http://127.0.0.1:5678/healthz') -join '\n'; "
            "[pscustomobject]@{ uptime_since_utc = $os.LastBootUpTime.ToUniversalTime().ToString('o'); bios = $bios.SMBIOSBIOSVersion; battery = $battery; reboot_required = $rebootRequired; active_hours_start = $updateSettings.ActiveHoursStart; active_hours_end = $updateSettings.ActiveHoursEnd; smart_active_hours = $updateSettings.SmartActiveHoursState; bitlocker = $bitlocker; active_scheme = $scheme; ac_sleep = $sleep; ac_hibernate = $hibernate; wsl = $wsl; lab = $lab } | ConvertTo-Json -Depth 4 -Compress"
        ),
    },
    "forex_m3_probe_directory_prepare": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$root = Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe'; "
            "if (-not (Test-Path -LiteralPath $root -PathType Container)) { throw 'Expected fixed Forex M1/M3 probe directory is absent.' }; "
            "$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name; "
            "& icacls.exe $root /grant \"$user`:(OI)(CI)M\" /T /C | Out-String | Out-Null; "
            "if ($LASTEXITCODE -ne 0) { throw \"icacls failed with exit code $LASTEXITCODE\" }; "
            "[pscustomobject]@{ path = $root; principal = $user; modify_access_granted = $true } | ConvertTo-Json -Compress"
        ),
    },
    "forex_m3_probe_directory_write_check": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$root = Join-Path $env:USERPROFILE 'Documents\\Code\\forex-m1-probe'; "
            "if (-not (Test-Path -LiteralPath $root -PathType Container)) { throw 'Expected fixed Forex M1/M3 probe directory is absent.' }; "
            "$path = Join-Path $root '__cs_ai_lab_m3_write_check.tmp'; "
            "try { [IO.File]::WriteAllText($path, 'fixed-write-check', [Text.Encoding]::UTF8); $readBack = [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8); if ($readBack -ne 'fixed-write-check') { throw 'Write check content mismatch' } } finally { Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue }; "
            "[pscustomobject]@{ path = $root; write_delete_check = $true } | ConvertTo-Json -Compress"
        ),
    },
    "m5_boot_startup_compatibility": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$distro = (wsl.exe --list --verbose) -join '\n'; "
            "$task = Get-ScheduledTask -TaskName 'CS AI Lab Start' -ErrorAction SilentlyContinue; "
            "$taskSummary = if ($null -eq $task) { $null } else { [pscustomobject]@{ state = $task.State.ToString(); principal = $task.Principal.UserId; logon_type = $task.Principal.LogonType.ToString(); triggers = (($task.Triggers | ForEach-Object { $_.CimClass.CimClassName }) -join ',') } }; "
            "[pscustomobject]@{ wsl_executable = [bool](Get-Command wsl.exe -ErrorAction SilentlyContinue); current_user_distributions = $distro; existing_startup_task = $taskSummary } | ConvertTo-Json -Depth 4 -Compress"
        ),
    },
    "m5_boot_system_wsl_probe": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$stateDir = Join-Path $env:ProgramData 'CSAILab'; New-Item -ItemType Directory -Force -Path $stateDir | Out-Null; "
            "$scriptPath = Join-Path $stateDir 'm5-system-wsl-probe.ps1'; $outputPath = Join-Path $stateDir 'm5-system-wsl-probe.txt'; $taskName = 'CS AI Lab M5 System WSL Probe'; "
            "$script = '$ErrorActionPreference = ''Continue''; whoami | Out-File -FilePath ''' + $outputPath + ''' -Encoding utf8; wsl.exe --list --verbose 2>&1 | Out-File -FilePath ''' + $outputPath + ''' -Encoding utf8 -Append'; "
            "$payload = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script)); "
            "$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand ' + $payload); "
            "$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)); "
            "$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest; "
            "Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null; "
            "Start-ScheduledTask -TaskName $taskName; Start-Sleep -Seconds 8; "
            "$info = Get-ScheduledTaskInfo -TaskName $taskName; $output = if (Test-Path $outputPath) { Get-Content -Raw $outputPath } else { 'probe-output-absent' }; "
            "Unregister-ScheduledTask -TaskName $taskName -Confirm:$false; Remove-Item -Force $scriptPath,$outputPath -ErrorAction SilentlyContinue; "
            "[pscustomobject]@{ task_last_result = $info.LastTaskResult; system_wsl_output = $output; task_removed = -not (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) } | ConvertTo-Json -Compress"
        ),
    },
    "m5_boot_s4u_wsl_probe": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$stateDir = Join-Path $env:ProgramData 'CSAILab'; New-Item -ItemType Directory -Force -Path $stateDir | Out-Null; "
            "$outputPath = Join-Path $stateDir 'm5-s4u-wsl-probe.txt'; $taskName = 'CS AI Lab M5 S4U WSL Probe'; "
            "$script = '$ErrorActionPreference = ''Continue''; whoami | Out-File -FilePath ''' + $outputPath + ''' -Encoding utf8; wsl.exe --list --verbose 2>&1 | Out-File -FilePath ''' + $outputPath + ''' -Encoding utf8 -Append'; "
            "$payload = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script)); "
            "$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand ' + $payload); "
            "$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)); "
            "$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest; "
            "Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null; "
            "Start-ScheduledTask -TaskName $taskName; Start-Sleep -Seconds 8; "
            "$info = Get-ScheduledTaskInfo -TaskName $taskName; $output = if (Test-Path $outputPath) { Get-Content -Raw $outputPath } else { 'probe-output-absent' }; "
            "Unregister-ScheduledTask -TaskName $taskName -Confirm:$false; Remove-Item -Force $outputPath -ErrorAction SilentlyContinue; "
            "[pscustomobject]@{ task_last_result = $info.LastTaskResult; s4u_wsl_output = $output; task_removed = -not (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) } | ConvertTo-Json -Compress"
        ),
    },
    "m5_boot_startup_enable": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$stateDir = Join-Path $env:ProgramData 'CSAILab'; New-Item -ItemType Directory -Force -Path $stateDir | Out-Null; "
            "$taskName = 'CS AI Lab Start'; $rollbackPath = Join-Path $stateDir 'CS-AI-Lab-Start.pre-m5.xml'; "
            "$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue; if ($null -ne $existing) { Export-ScheduledTask -TaskName $taskName | Set-Content -Path $rollbackPath -Encoding utf8 }; "
            "$bashCommand = 'for attempt in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 2; done; docker info >/dev/null; cd /home/chris/projects/cs-ai-lab-infra; docker compose up -d n8n health_dashboard; exec tail -f /dev/null'; "
            "$bashPayload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bashCommand)); "
            "$launcher = '$ErrorActionPreference = ''Stop''; $arguments = ''-d Ubuntu -- bash -c ""echo ' + $bashPayload + ' | base64 -d | bash""''; Start-Process -FilePath ''wsl.exe'' -ArgumentList $arguments -WindowStyle Hidden'; "
            "$payload = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($launcher)); "
            "$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand ' + $payload); "
            "$trigger = New-ScheduledTaskTrigger -AtStartup; $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest; "
            "$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -MultipleInstances IgnoreNew; "
            "Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Starts the private Ubuntu WSL n8n and PostgreSQL lab at Windows boot using passwordless S4U; WSL stays alive.' -Force | Out-Null; "
            "$task = Get-ScheduledTask -TaskName $taskName; [pscustomobject]@{ task_name = $task.TaskName; principal = $task.Principal.UserId; logon_type = $task.Principal.LogonType.ToString(); triggers = (($task.Triggers | ForEach-Object { $_.CimClass.CimClassName }) -join ','); rollback_saved = Test-Path $rollbackPath } | ConvertTo-Json -Compress"
        ),
    },
    "m5_boot_startup_status": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; $task = Get-ScheduledTask -TaskName 'CS AI Lab Start'; $info = Get-ScheduledTaskInfo -TaskName 'CS AI Lab Start'; "
            "[pscustomobject]@{ principal = $task.Principal.UserId; logon_type = $task.Principal.LogonType.ToString(); triggers = (($task.Triggers | ForEach-Object { $_.CimClass.CimClassName }) -join ','); state = $task.State.ToString(); last_result = $info.LastTaskResult } | ConvertTo-Json -Compress"
        ),
    },
    "wsl_status": {
        "approval_required": False,
        "command": "$ErrorActionPreference = 'Stop'; wsl.exe --status; wsl.exe --list --verbose",
    },
    "docker_status": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "wsl.exe -d Ubuntu -- bash -lc 'docker --version && docker compose version && docker info >/dev/null && echo docker-daemon-ok'"
        ),
    },
    "docker_preflight": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "wsl.exe -d Ubuntu -- bash -lc 'dpkg-query -W docker.io docker-compose docker-compose-v2 docker-doc "
            "docker-buildx podman-docker containerd runc 2>/dev/null || true'"
        ),
    },
    "docker_install_diagnostics": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "wsl.exe -d Ubuntu -- bash -lc 'set -e; "
            "echo ---docker-source---; test -f /etc/apt/sources.list.d/docker.sources && "
            "cat /etc/apt/sources.list.d/docker.sources || echo absent; "
            "echo ---docker-packages---; apt-cache policy docker-ce docker-ce-cli containerd.io || true; "
            "echo ---recent-apt-log---; test -f /var/log/apt/term.log && tail -n 80 /var/log/apt/term.log || true'"
        ),
    },
    "docker_repository_probe": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "wsl.exe -d Ubuntu -- curl --fail --silent --show-error --location --max-time 20 "
            "--output /dev/null --write-out 'HTTP %{http_code}' https://download.docker.com/linux/ubuntu/gpg"
        ),
    },
    "wsl_stdin_probe": {
        "approval_required": False,
        "wsl_script": "printf 'wsl-stdin-ok\\n'\n",
    },
    "startup_status": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$task = Get-ScheduledTask -TaskName 'CS AI Lab Start' -ErrorAction SilentlyContinue; "
            "if ($null -eq $task) { '[{\"present\":false}]' } else { "
            "$info = Get-ScheduledTaskInfo -TaskName 'CS AI Lab Start'; "
            "[pscustomobject]@{ present = $true; state = $task.State.ToString(); "
            "last_run_time = $info.LastRunTime.ToUniversalTime().ToString('o'); "
            "last_task_result = $info.LastTaskResult } | ConvertTo-Json -Compress }"
        ),
    },
    "startup_enable": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$stateDir = Join-Path $env:ProgramData 'CSAILab'; New-Item -ItemType Directory -Force -Path $stateDir | Out-Null; "
            "$scriptPath = Join-Path $stateDir 'start-wsl-lab.ps1'; "
            "$script = @'\n"
            "$ErrorActionPreference = 'Stop'\n"
            "$stateDir = Join-Path $env:ProgramData 'CSAILab'\n"
            "$stdoutPath = Join-Path $stateDir 'wsl-keepalive.stdout.log'\n"
            "$stderrPath = Join-Path $stateDir 'wsl-keepalive.stderr.log'\n"
            "$bashCommand = 'for attempt in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 2; done; docker info >/dev/null; cd /home/chris/projects/cs-ai-lab-infra; docker compose up -d n8n health_dashboard; exec tail -f /dev/null'\n"
            "$payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bashCommand))\n"
            "$arguments = '-d Ubuntu -- bash -c \"echo ' + $payload + ' | base64 -d | bash\"'\n"
            "Start-Process -FilePath 'wsl.exe' -ArgumentList $arguments -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath\n"
            "'@; Set-Content -Path $scriptPath -Value $script -Encoding utf8; "
            "$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"' + $scriptPath + '\"'); "
            "$trigger = New-ScheduledTaskTrigger -AtLogOn; "
            "Register-ScheduledTask -TaskName 'CS AI Lab Start' -Action $action -Trigger $trigger "
            "-Description 'Starts T480 Ubuntu WSL, waits for Docker, starts private PostgreSQL, n8n, and the status-only dashboard, and keeps WSL alive at sign-in.' -Force | Out-Null; "
            "Get-ScheduledTask -TaskName 'CS AI Lab Start' | Select-Object TaskName,State | ConvertTo-Json -Compress"
        ),
    },
    "startup_run": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "Start-ScheduledTask -TaskName 'CS AI Lab Start'; "
            "Start-Sleep -Seconds 10; "
            "$task = Get-ScheduledTask -TaskName 'CS AI Lab Start'; "
            "[pscustomobject]@{ task_state = $task.State.ToString(); "
            "n8n_health = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 http://127.0.0.1:5678/healthz).StatusCode; "
            "health_dashboard = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 http://127.0.0.1:8080/healthz).StatusCode } | ConvertTo-Json -Compress"
        ),
    },
    "startup_disable": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "Unregister-ScheduledTask -TaskName 'CS AI Lab Start' -Confirm:$false -ErrorAction SilentlyContinue; "
            "'{\"removed\":true}'"
        ),
    },
    "startup_diagnostics": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$stdoutPath = Join-Path $env:ProgramData 'CSAILab\\wsl-keepalive.stdout.log'; "
            "$stderrPath = Join-Path $env:ProgramData 'CSAILab\\wsl-keepalive.stderr.log'; "
            "$scriptPath = Join-Path $env:ProgramData 'CSAILab\\start-wsl-lab.ps1'; "
            "Get-ScheduledTaskInfo -TaskName 'CS AI Lab Start' | Select-Object LastRunTime,LastTaskResult | ConvertTo-Json -Compress; "
            "Get-ScheduledTask -TaskName 'CS AI Lab Start' | Select-Object -ExpandProperty Actions | Select-Object Execute,Arguments | ConvertTo-Json -Compress; "
            "if (Test-Path $scriptPath) { Get-Content $scriptPath } else { 'startup-script-absent' }; "
            "if (Test-Path $stdoutPath) { Get-Content -Tail 80 $stdoutPath } else { 'startup-stdout-absent' }; "
            "if (Test-Path $stderrPath) { Get-Content -Tail 80 $stderrPath } else { 'startup-stderr-absent' }"
        ),
    },
    "docker_runtime_evidence": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "systemctl is-active docker\n"
            "apt-cache policy docker-ce | sed -n '1,4p'\n"
            "docker --version\n"
            "docker compose version\n"
            "docker info >/dev/null\n"
            "echo docker-daemon-ok\n"
        ),
    },
    "docker_hello_world": {
        "approval_required": True,
        "wsl_script": "set -euo pipefail\ndocker run --rm hello-world\n",
    },
    "ollama_embeddings_status": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "echo ---ollama-container---\n"
            "docker compose --profile ollama ps ollama\n"
            "if docker compose --profile ollama ps --status running --services | grep -qx ollama; then\n"
            "  echo ---ollama-models---\n"
            "  docker compose exec -T ollama ollama list || true\n"
            "else\n"
            "  echo ollama-not-running\n"
            "fi\n"
            "echo ---installation-job---\n"
            "if [ -f /home/chris/.local/state/cs-ai-lab/ollama-embeddings-install.pid ] && "
            "kill -0 \"$(cat /home/chris/.local/state/cs-ai-lab/ollama-embeddings-install.pid)\" 2>/dev/null; then\n"
            "  echo running\n"
            "else\n"
            "  echo not-running\n"
            "fi\n"
            "echo ---installation-log---\n"
            "test -f /home/chris/.local/state/cs-ai-lab/ollama-embeddings-install.log && "
            "tail -n 40 /home/chris/.local/state/cs-ai-lab/ollama-embeddings-install.log || echo absent\n"
        ),
    },
    "ollama_embeddings_install": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "state_dir=/home/chris/.local/state/cs-ai-lab\n"
            "mkdir -p \"$state_dir\"\n"
            "job_pid_file=\"$state_dir/ollama-embeddings-install.pid\"\n"
            "job_log_file=\"$state_dir/ollama-embeddings-install.log\"\n"
            "if [ -f \"$job_pid_file\" ] && kill -0 \"$(cat \"$job_pid_file\")\" 2>/dev/null; then\n"
            "  echo ollama-embeddings-install-already-running\n"
            "  exit 0\n"
            "fi\n"
            "nohup bash -c 'set -euo pipefail; cd /home/chris/projects/cs-ai-lab-infra; "
            "docker compose --profile ollama config --quiet; docker compose --profile ollama pull ollama; "
            "docker compose --profile ollama up -d --wait --wait-timeout 180 ollama; "
            "docker compose exec -T ollama ollama pull bge-m3; "
            "docker compose exec -T ollama ollama pull mxbai-embed-large' "
            ">\"$job_log_file\" 2>&1 &\n"
            "echo $! > \"$job_pid_file\"\n"
            "echo ollama-embeddings-install-started\n"
        ),
    },
    "ollama_embeddings_diagnostics": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "log_file=/home/chris/.local/state/cs-ai-lab/ollama-embeddings-install.log\n"
            "if [ -f \"$log_file\" ]; then\n"
            "  tail -n 80 \"$log_file\"\n"
            "else\n"
            "  echo no-ollama-embedding-install-log\n"
            "fi\n"
        ),
    },
    "m2_preflight": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "echo ---identity---\n"
            "whoami\n"
            "pwd\n"
            "echo ---capacity---\n"
            "df -h /\n"
            "echo ---docker---\n"
            "docker --version\n"
            "docker compose version\n"
            "echo ---deployment-prerequisites---\n"
            "command -v git\n"
            "command -v openssl\n"
            "echo ---deployment-path---\n"
            "if [ -d /home/chris/projects/cs-ai-lab-infra ]; then\n"
            "  echo present\n"
            "  git -C /home/chris/projects/cs-ai-lab-infra rev-parse --short HEAD 2>/dev/null || true\n"
            "else\n"
            "  echo absent\n"
            "fi\n"
            "echo ---existing-lab-containers---\n"
            "docker ps -a --filter label=com.docker.compose.project=cs-ai-lab --format '{{.Names}} {{.Status}}'\n"
        ),
    },
    "m2_deploy": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "repository_url='https://github.com/successbycs/cs-ai-lab-infra.git'\n"
            "deployment_root='/home/chris/projects/cs-ai-lab-infra'\n"
            "if [[ -e \"$deployment_root\" ]]; then\n"
            "  printf 'Refusing M2 deployment: target already exists: %s\\n' \"$deployment_root\" >&2\n"
            "  exit 4\n"
            "fi\n"
            "mkdir -p /home/chris/projects\n"
            "git clone --branch main --depth 1 \"$repository_url\" \"$deployment_root\"\n"
            "cd \"$deployment_root\"\n"
            "umask 077\n"
            "cp .env.example .env\n"
            "postgres_password=\"$(openssl rand -hex 32)\"\n"
            "n8n_encryption_key=\"$(openssl rand -hex 32)\"\n"
            "sed -i \"s/CHANGE_ME_TO_A_LONG_UNIQUE_PASSWORD/$postgres_password/\" .env\n"
            "sed -i \"s/CHANGE_ME_TO_A_LONG_RANDOM_VALUE/$n8n_encryption_key/\" .env\n"
            "chmod 600 .env\n"
            "./scripts/bootstrap.sh\n"
            "docker compose config --quiet\n"
            "docker compose pull\n"
            "docker compose up -d --wait --wait-timeout 180\n"
            "git rev-parse HEAD\n"
        ),
    },
    "m2_deploy_diagnostics": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "echo ---revision---\n"
            "git rev-parse --short HEAD\n"
            "echo ---env-permissions---\n"
            "stat -c '%a %n' .env\n"
            "echo ---compose-validation---\n"
            "docker compose config --quiet\n"
            "echo valid\n"
            "echo ---configured-images---\n"
            "docker compose config --images\n"
            "echo ---local-images---\n"
            "docker compose images\n"
            "echo ---containers---\n"
            "docker compose ps -a\n"
        ),
    },
    "lab_services_start": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "docker compose up -d --wait --wait-timeout 180 n8n health_dashboard\n"
            "docker compose ps n8n postgres health_dashboard\n"
        ),
    },
    "n8n_restart": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "docker compose restart n8n\n"
            "for attempt in $(seq 1 30); do\n"
            "  if curl --fail --silent --max-time 5 http://127.0.0.1:5678/healthz >/dev/null; then\n"
            "    docker compose ps n8n\n"
            "    exit 0\n"
            "  fi\n"
            "  sleep 2\n"
            "done\n"
            "printf 'n8n did not become healthy after restart.\\n' >&2\n"
            "exit 1\n"
        ),
    },
    "n8n_internal_task_runners_enable": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "grep -Fq 'N8N_RUNNERS_ENABLED:' compose.yaml || sed -i '/N8N_PERSONALIZATION_ENABLED:/a\\      N8N_RUNNERS_ENABLED: ${N8N_RUNNERS_ENABLED:-true}' compose.yaml\n"
            "if grep -q '^N8N_RUNNERS_ENABLED=' .env; then sed -i 's/^N8N_RUNNERS_ENABLED=.*/N8N_RUNNERS_ENABLED=true/' .env; else printf '\\nN8N_RUNNERS_ENABLED=true\\n' >> .env; fi\n"
            "docker compose up -d --force-recreate n8n\n"
            "for attempt in $(seq 1 45); do\n"
            "  if curl --fail --silent --max-time 5 http://127.0.0.1:5678/healthz >/dev/null; then\n"
            "    docker compose exec -T n8n sh -lc 'test \"$N8N_RUNNERS_ENABLED\" = true'\n"
            "    exit 0\n"
            "  fi\n"
            "  sleep 2\n"
            "done\n"
            "printf 'n8n task runners did not become ready.\\n' >&2\n"
            "exit 1\n"
        ),
    },
    "lab_health": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "./scripts/health-check.sh\n"
        ),
    },
    "lab_runtime_diagnostics": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "echo ---compose-status---\n"
            "docker compose ps -a\n"
            "echo ---docker-memory---\n"
            "free -h\n"
            "echo ---n8n-logs---\n"
            "docker compose logs --tail 80 n8n\n"
            "echo ---postgres-logs---\n"
            "docker compose logs --tail 80 postgres\n"
            "echo ---ollama-logs---\n"
            "docker compose --profile ollama logs --tail 80 ollama\n"
        ),
    },
    "n8n_upgrade_preflight": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "echo ---current-container-image---\n"
            "docker compose images n8n\n"
            "echo ---reviewed-target-image---\n"
            "docker compose config --images | grep '^n8nio/n8n:'\n"
            "echo ---current-version---\n"
            "docker compose exec -T n8n n8n --version </dev/null\n"
            "echo ---private-port-binding---\n"
            "docker compose ps n8n --format json\n"
            "echo ---service-health---\n"
            "docker compose ps n8n postgres\n"
            "echo ---capacity---\n"
            "df -h /\n"
        ),
    },
    "n8n_upgrade_backup": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "./scripts/backup.sh\n"
            "backup_file=\"$(find postgres/backup -maxdepth 1 -type f -name '*.sql.gz' -printf '%T@ %p\\n' | sort -nr | head -n 1 | cut -d' ' -f2-)\"\n"
            "[[ -n \"$backup_file\" && -f \"$backup_file\" ]] || { printf 'No PostgreSQL backup was created.\\n' >&2; exit 4; }\n"
            "gzip -t \"$backup_file\"\n"
            "printf 'backup_file=%s\\n' \"$backup_file\"\n"
            "sha256sum \"$backup_file\"\n"
        ),
    },
    "n8n_upgrade": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "expected_image='n8nio/n8n:1.123.65@sha256:8554136778e759f208205d13bf52ce0c782c43fefd72ecaab2b88285d7bc8046'\n"
            "configured_image=\"$(docker compose config --images | grep '^n8nio/n8n:' | head -n 1)\"\n"
            "[[ \"$configured_image\" == \"$expected_image\" ]] || { printf 'Refusing upgrade: reviewed n8n image does not match Compose configuration.\\n' >&2; exit 4; }\n"
            "docker compose pull n8n n8n_files_init </dev/null\n"
            "docker compose up -d --wait --wait-timeout 180 n8n </dev/null\n"
            "docker compose exec -T n8n n8n --version </dev/null\n"
            "docker compose ps n8n postgres\n"
        ),
    },
    "m2_latest_evidence_manifest": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "bundle_dir=\"$(find evidence/M2 -mindepth 1 -maxdepth 1 -type d -printf '%f\\n' | sort | tail -n 1)\"\n"
            "[[ -n \"$bundle_dir\" ]] || { printf 'No M2 evidence bundle exists.\\n' >&2; exit 4; }\n"
            "bundle_path=\"evidence/M2/$bundle_dir\"\n"
            "./scripts/verify-m2-evidence.sh \"$bundle_path\"\n"
            "sha256sum \"$bundle_path/SHA256SUMS\"\n"
        ),
    },
    "repository_update": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "repository_root='/home/chris/projects/cs-ai-lab-infra'\n"
            "cd \"$repository_root\"\n"
            "git diff --quiet || { printf 'Refusing update: tracked working-tree changes exist.\\n' >&2; exit 4; }\n"
            "git diff --cached --quiet || { printf 'Refusing update: staged changes exist.\\n' >&2; exit 4; }\n"
            "test -z \"$(git status --porcelain --untracked-files=normal)\" || { printf 'Refusing update: untracked files exist.\\n' >&2; exit 4; }\n"
            "git fetch origin main\n"
            "git merge --ff-only origin/main\n"
            "git rev-parse HEAD\n"
        ),
    },
    "repository_status": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "git status --short --untracked-files=normal\n"
            "git rev-parse HEAD\n"
            "git rev-parse origin/main\n"
        ),
    },
    "repository_diff": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "git diff -- scripts/t480_adapter.py t480/command-catalog.json t480/README.md\n"
        ),
    },
    "repository_repair": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "repository_root='/home/chris/projects/cs-ai-lab-infra'\n"
            "cd \"$repository_root\"\n"
            "[[ \"$(git remote get-url origin)\" == 'https://github.com/successbycs/cs-ai-lab-infra.git' ]] || { printf 'Refusing repair: origin differs.\\n' >&2; exit 4; }\n"
            "backup_root=\".git/corrupt-object-backup-$(date -u +%Y%m%dT%H%M%SZ)\"\n"
            "mapfile -t empty_objects < <(find .git/objects -type f -size 0c -print)\n"
            "((${#empty_objects[@]} > 0)) || { printf 'No zero-byte Git objects found; refusing repair.\\n' >&2; exit 4; }\n"
            "mkdir -p \"$backup_root\"\n"
            "for object in \"${empty_objects[@]}\"; do relative=\"${object#.git/}\"; mkdir -p \"$backup_root/$(dirname \"$relative\")\"; mv \"$object\" \"$backup_root/$relative\"; done\n"
            "git fetch --force origin main\n"
            "git fsck --no-reflogs --no-dangling\n"
            "git diff --quiet && git diff --cached --quiet && test -z \"$(git status --porcelain --untracked-files=normal)\" || { printf 'Git repaired but checkout is not clean; refusing update.\\n' >&2; exit 4; }\n"
            "git merge --ff-only origin/main\n"
            "printf 'REPOSITORY_REPAIR_OK revision=%s backed_up_zero_byte_objects=%s\\n' \"$(git rev-parse HEAD)\" \"${#empty_objects[@]}\"\n"
        ),
    },
    "repository_restore_corrupt_contract_files": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "files=(scripts/t480_adapter.py t480/command-catalog.json t480/README.md)\n"
            "for file in \"${files[@]}\"; do [[ -f \"$file\" && ! -s \"$file\" ]] || { printf 'Refusing restore: %s is not a zero-byte file.\\n' \"$file\" >&2; exit 4; }; done\n"
            "git show origin/main:scripts/t480_adapter.py >/dev/null\n"
            "git checkout origin/main -- \"${files[@]}\"\n"
            "git diff --quiet && git diff --cached --quiet && test -z \"$(git status --porcelain --untracked-files=normal)\" || { printf 'Restore completed but checkout is not clean; refusing update.\\n' >&2; exit 4; }\n"
            "git merge --ff-only origin/main\n"
            "printf 'REPOSITORY_CONTRACT_FILES_RESTORED revision=%s files=%s\\n' \"$(git rev-parse HEAD)\" \"${#files[@]}\"\n"
        ),
    },
    "repository_finalize_corrupt_contract_restore": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "expected=$'scripts/t480_adapter.py\\nt480/README.md\\nt480/command-catalog.json'\n"
            "[[ \"$(git diff --cached --name-only)\" == \"$expected\" ]] || { printf 'Refusing finalize: staged paths differ from the three restored contract files.\\n' >&2; exit 4; }\n"
            "git diff --quiet || { printf 'Refusing finalize: unstaged changes exist.\\n' >&2; exit 4; }\n"
            "git diff --cached --quiet origin/main -- scripts/t480_adapter.py t480/README.md t480/command-catalog.json || { printf 'Refusing finalize: restored files differ from fetched origin/main.\\n' >&2; exit 4; }\n"
            "git reset --mixed origin/main\n"
            "test -z \"$(git status --porcelain --untracked-files=normal)\" || { printf 'Finalize did not produce a clean checkout.\\n' >&2; exit 5; }\n"
            "printf 'REPOSITORY_RESTORE_FINALIZED revision=%s\\n' \"$(git rev-parse HEAD)\"\n"
        ),
    },
    "forex_deploy": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            f"repository_root='{FOREX_REMOTE_ROOT}'\n"
            f"repository_url='{FOREX_REPOSITORY}'\n"
            f"expected_revision='{FOREX_REVISION}'\n"
            "if [[ -e \"$repository_root\" && ! -d \"$repository_root/.git\" ]]; then\n"
            "  printf 'Refusing Forex deployment: target exists but is not a Git checkout.\\n' >&2; exit 4\n"
            "fi\n"
            "if [[ -d \"$repository_root/.git\" ]]; then\n"
            "  cd \"$repository_root\"\n"
            "  git diff --quiet && git diff --cached --quiet && test -z \"$(git status --porcelain --untracked-files=normal)\" || { printf 'Refusing Forex deployment: target checkout is not clean.\\n' >&2; exit 4; }\n"
            "  [[ \"$(git remote get-url origin)\" == \"$repository_url\" ]] || { printf 'Refusing Forex deployment: origin differs.\\n' >&2; exit 4; }\n"
            "else\n"
            "  mkdir -p \"$(dirname \"$repository_root\")\"\n"
            "  git clone --no-checkout \"$repository_url\" \"$repository_root\"\n"
            "  cd \"$repository_root\"\n"
            "fi\n"
            "git fetch --depth 1 origin \"$expected_revision\"\n"
            "git checkout --detach \"$expected_revision\"\n"
            "[[ \"$(git rev-parse HEAD)\" == \"$expected_revision\" ]] || { printf 'Forex deployment revision mismatch.\\n' >&2; exit 5; }\n"
            "test -f sql/migrations/001_m2_historical_data.sql\n"
            "test -f scripts/build_m2_postgres_import.py\n"
            "mkdir -p /mnt/c/Users/chris/ForexEvidence\n"
            "printf 'FOREX_DEPLOY_OK revision=%s\\n' \"$expected_revision\"\n"
        ),
    },
    "forex_stage_m1_evidence": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            f"staged='/mnt/c/Users/chris/ForexEvidence/capture.stdout.json'\n"
            f"destination='{FOREX_M1_CAPTURE_REMOTE}'\n"
            f"expected_sha256='{FOREX_M1_CAPTURE_SHA256}'\n"
            "test -d /home/chris/projects/forex/.git || { printf 'Forex checkout is absent.\\n' >&2; exit 4; }\n"
            "test -f \"$staged\" || { printf 'Fixed M1 capture is absent from Windows staging.\\n' >&2; exit 4; }\n"
            "actual_sha256=\"$(sha256sum \"$staged\" | head -c 64)\"\n"
            "[[ \"$actual_sha256\" == \"$expected_sha256\" ]] || { printf 'Fixed M1 capture hash differs from the reviewed payload.\\n' >&2; exit 5; }\n"
            "mkdir -p \"$(dirname \"$destination\")\"\n"
            "install -m 0600 \"$staged\" \"$destination\"\n"
            "rm -f \"$staged\"\n"
            "printf 'FOREX_M1_EVIDENCE_STAGED sha256:%s\\n' \"$actual_sha256\"\n"
        ),
    },
    "m3_recovery_proof": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "./scripts/m3-recovery-proof.sh\n"
        ),
    },
    "m3_latest_evidence_manifest": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "bundle_dir=\"$(find evidence/M3 -mindepth 1 -maxdepth 1 -type d -printf '%f\\n' | sort | tail -n 1)\"\n"
            "[[ -n \"$bundle_dir\" ]] || { printf 'No M3 evidence bundle exists.\\n' >&2; exit 4; }\n"
            "bundle_path=\"evidence/M3/$bundle_dir\"\n"
            "./scripts/verify-m3-recovery-evidence.sh \"$bundle_path\"\n"
            "sha256sum \"$bundle_path/SHA256SUMS\"\n"
        ),
    },
    "transcription_preflight": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            f"repository_root='{TRANSCRIBER_ROOT}'\n"
            "test -f \"$repository_root/compose.yaml\" || { printf 'Transcriber repository is absent on the T480.\\n' >&2; exit 4; }\n"
            "test -f \"$repository_root/.env\" || { printf 'Transcriber .env is absent on the T480.\\n' >&2; exit 4; }\n"
            "test -d \"$repository_root/incoming\" || { printf 'Transcriber incoming directory is absent.\\n' >&2; exit 4; }\n"
            "test -d \"$repository_root/outputs\" || { printf 'Transcriber output directory is absent.\\n' >&2; exit 4; }\n"
            "cd \"$repository_root\"\n"
            "docker compose --profile transcribe config --quiet\n"
            "if docker image inspect mp4-to-transcript-transcriber >/dev/null 2>&1; then printf 'transcriber_image=present\\n'; else printf 'transcriber_image=not_present; submit will build it on demand\\n'; fi\n"
            "printf 'incoming_count=%s\\n' \"$(find \"$repository_root/incoming\" -maxdepth 1 -type f -iname '*.mp4' -printf . | wc -c)\"\n"
            "printf 'transcriber_preflight=ok\\n'\n"
        ),
    },
    "transcription_diagnostics": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            f"cd '{TRANSCRIBER_ROOT}'\n"
            "printf '%s\\n' '--- transcriber-containers ---'\n"
            "docker compose --profile transcribe ps -a\n"
            "printf '%s\\n' '--- inbox ---'\n"
            "find incoming -maxdepth 1 -type f -iname '*.mp4' -printf '%f\\n' | sort\n"
            "printf '%s\\n' '--- latest-job ---'\n"
            "latest_job=\"$(find outputs -mindepth 2 -maxdepth 2 -name job.json -printf '%T@ %p\\n' | sort -nr | head -n 1 | cut -d' ' -f2-)\"\n"
            "if [[ -n \"$latest_job\" ]]; then cat \"$latest_job\"; else printf 'no_job_metadata_yet\\n'; fi\n"
            "printf '%s\\n' '--- running-jobs ---'\n"
            "python3 - <<'PY'\n"
            "import json\n"
            "from pathlib import Path\n"
            "running = []\n"
            "for path in Path('outputs').glob('*/job.json'):\n"
            "    try: job = json.loads(path.read_text())\n"
            "    except (OSError, json.JSONDecodeError): continue\n"
            "    if job.get('status') == 'RUNNING': running.append({'job_id': job.get('job_id'), 'input_filename': job.get('input_filename'), 'started_at': job.get('started_at')})\n"
            "print(json.dumps(sorted(running, key=lambda job: (job.get('started_at') or ''))))\n"
            "PY\n"
        ),
    },
    "transcription_completed_hashes": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            f"cd '{TRANSCRIBER_ROOT}'\n"
            "python3 - <<'PY'\n"
            "import json\n"
            "from pathlib import Path\n"
            "hashes = []\n"
            "for path in Path('outputs').glob('*/job.json'):\n"
            "    try:\n"
            "        job = json.loads(path.read_text())\n"
            "    except (OSError, json.JSONDecodeError):\n"
            "        continue\n"
            "    if job.get('status') == 'REVIEW_REQUIRED' and job.get('input_sha256'):\n"
            "        hashes.append(job['input_sha256'])\n"
            "print(json.dumps(sorted(set(hashes))))\n"
            "PY\n"
        ),
    },
    "transcription_cleanup_completed_inbox": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            f"cd '{TRANSCRIBER_ROOT}'\n"
            "python3 - <<'PY'\n"
            "import hashlib\n"
            "import json\n"
            "from pathlib import Path\n"
            "completed = set()\n"
            "for metadata_path in Path('outputs').glob('*/job.json'):\n"
            "    try:\n"
            "        job = json.loads(metadata_path.read_text())\n"
            "    except (OSError, json.JSONDecodeError):\n"
            "        continue\n"
            "    if job.get('status') == 'REVIEW_REQUIRED' and job.get('input_sha256'):\n"
            "        completed.add(job['input_sha256'])\n"
            "removed = []\n"
            "for media_path in sorted(Path('incoming').glob('*.mp4')) + sorted(Path('incoming').glob('*.MP4')):\n"
            "    digest = hashlib.sha256(media_path.read_bytes()).hexdigest()\n"
            "    if digest in completed:\n"
            "        media_path.unlink()\n"
            "        removed.append(media_path.name)\n"
            "print(json.dumps({'removed_completed_inbox_copies': removed}))\n"
            "PY\n"
        ),
    },
    "transcription_export_prepare": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            f"cd '{TRANSCRIBER_ROOT}'\n"
            f"export_root='{TRANSCRIBER_WSL_EXPORT}'\n"
            "mkdir -p \"$export_root\"\n"
            "python3 - \"$export_root\" <<'PY'\n"
            "import json\n"
            "import shutil\n"
            "import sys\n"
            "from pathlib import Path\n"
            "export_root = Path(sys.argv[1])\n"
            "exported = []\n"
            "for metadata_path in sorted(Path('outputs').glob('*/job.json')):\n"
            "    try:\n"
            "        job = json.loads(metadata_path.read_text())\n"
            "    except (OSError, json.JSONDecodeError):\n"
            "        continue\n"
            "    if job.get('status') != 'REVIEW_REQUIRED':\n"
            "        continue\n"
            "    source_filename = str(job.get('input_filename', ''))\n"
            "    source_stem = Path(source_filename).stem\n"
            "    if not source_stem or Path(source_stem).name != source_stem:\n"
            "        raise ValueError(f'Unsafe source filename in job metadata: {source_filename!r}')\n"
            "    destination = export_root / source_stem\n"
            "    if destination.exists():\n"
            "        existing_metadata = destination / 'job.json'\n"
            "        if not existing_metadata.is_file() or json.loads(existing_metadata.read_text()).get('job_id') != job.get('job_id'):\n"
            "            raise ValueError(f'Export folder collision: {destination.name}')\n"
            "    shutil.copytree(metadata_path.parent, destination, dirs_exist_ok=True)\n"
            "    exported.append(destination.name)\n"
            "print(json.dumps({'prepared_review_jobs': exported}))\n"
            "PY\n"
        ),
    },
    "transcription_deploy": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            f"repository_root='{TRANSCRIBER_ROOT}'\n"
            "repository_parent='/home/chris/projects'\n"
            "repository_url='https://github.com/successbycs/mp4-to-transcript.git'\n"
            "mkdir -p \"$repository_parent\"\n"
            "if [[ -d \"$repository_root/.git\" ]]; then\n"
            "  cd \"$repository_root\"\n"
            "  git diff --quiet && git diff --cached --quiet && test -z \"$(git status --porcelain --untracked-files=normal)\" || { printf 'Refusing deploy: transcriber checkout is not clean.\\n' >&2; exit 4; }\n"
            "  git fetch origin main\n"
            "  git merge --ff-only origin/main\n"
            "else\n"
            "  test ! -e \"$repository_root\" || { printf 'Refusing deploy: transcriber path exists but is not a Git checkout.\\n' >&2; exit 4; }\n"
            "  git clone \"$repository_url\" \"$repository_root\"\n"
            "  cd \"$repository_root\"\n"
            "fi\n"
            "test -f .env || cp .env.example .env\n"
            "mkdir -p incoming outputs\n"
            "docker compose --profile transcribe build\n"
            "git rev-parse HEAD\n"
            "printf 'transcriber_deploy=ok\\n'\n"
        ),
    },
    "transcription_prepare": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            f"repository_root='{TRANSCRIBER_ROOT}'\n"
            "test -f \"$repository_root/compose.yaml\" || { printf 'Transcriber repository is absent on the T480.\\n' >&2; exit 4; }\n"
            "mkdir -p \"$repository_root/incoming\" \"$repository_root/outputs\"\n"
            "cd \"$repository_root\"\n"
            "docker compose --profile transcribe build\n"
            "printf 'transcriber_prepared=ok\\n'\n"
        ),
    },
    "transcription_windows_staging_prepare": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "New-Item -ItemType Directory -Force -Path 'C:\\Users\\chris\\TranscriptionInbox' | Out-Null; "
            "if ((Get-ChildItem -LiteralPath 'C:\\Users\\chris\\TranscriptionInbox' -File -Filter '*.mp4').Count -ne 0) "
            "{ throw 'Transcription Windows staging folder is not empty.' }; "
            "'{\"transcription_windows_staging\":\"ready\"}'"
        ),
    },
    "transcription_model_prefetch": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            f"cd '{TRANSCRIBER_ROOT}'\n"
            "docker compose --profile transcribe run --rm --entrypoint python -e WHISPER_LOCAL_FILES_ONLY=false transcriber -c \"from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8', download_root='/data/model-cache', local_files_only=False, cpu_threads=4, num_workers=1); print('transcription_model_cache=base-int8-ready')\"\n"
        ),
    },
    "transcription_process_next": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            f"repository_root='{TRANSCRIBER_ROOT}'\n"
            f"windows_staging='{TRANSCRIBER_WSL_STAGING}'\n"
            "cd \"$repository_root\"\n"
            "shopt -s nullglob\n"
            "staged_files=(\"$windows_staging\"/*.mp4 \"$windows_staging\"/*.MP4)\n"
            "if (( ${#staged_files[@]} != 1 )); then printf 'Expected exactly one staged MP4; found %s.\\n' \"${#staged_files[@]}\" >&2; exit 4; fi\n"
            "input_file=\"${staged_files[0]}\"\n"
            "input_name=\"${input_file##*/}\"\n"
            "mv -- \"$input_file\" \"incoming/$input_name\"\n"
            "input_file=\"incoming/$input_name\"\n"
            "printf 'transcription_input=%s\\n' \"$input_name\"\n"
            "TRANSCRIPT_INPUT_DIR=./incoming docker compose --profile transcribe run --rm transcriber transcribe \"/input/$input_name\"\n"
            "rm -- \"$input_file\"\n"
            "printf 'transcription_input_removed_after_success=%s\\n' \"$input_name\"\n"
        ),
    },
    "transcription_process_existing_inbox": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            f"cd '{TRANSCRIBER_ROOT}'\n"
            "shopt -s nullglob\n"
            "files=(incoming/*.mp4 incoming/*.MP4)\n"
            "if (( ${#files[@]} != 1 )); then printf 'Expected exactly one retained inbox MP4; found %s.\\n' \"${#files[@]}\" >&2; exit 4; fi\n"
            "input_file=\"${files[0]}\"\n"
            "input_name=\"${input_file##*/}\"\n"
            "printf 'transcription_recovery_input=%s\\n' \"$input_name\"\n"
            "TRANSCRIPT_INPUT_DIR=./incoming docker compose --profile transcribe run --rm transcriber transcribe \"/input/$input_name\"\n"
            "rm -- \"$input_file\"\n"
            "printf 'transcription_recovery_input_removed_after_success=%s\\n' \"$input_name\"\n"
        ),
    },
    "transcription_cancel_newest_duplicate": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            f"cd '{TRANSCRIBER_ROOT}'\n"
            "mapfile -t containers < <(docker ps -q --filter 'label=com.docker.compose.project=mp4-to-transcript' --filter 'label=com.docker.compose.service=transcriber')\n"
            "if (( ${#containers[@]} != 2 )); then printf 'Refusing duplicate cancellation: expected exactly two transcriber containers, found %s.\\n' \"${#containers[@]}\" >&2; exit 4; fi\n"
            "newest=\"$(docker inspect --format '{{.Created}} {{.Id}}' \"${containers[@]}\" | sort | tail -n 1 | awk '{print $2}')\"\n"
            "docker stop \"$newest\" >/dev/null\n"
            "python3 - <<'PY'\n"
            "import json\n"
            "from datetime import datetime, timezone\n"
            "from pathlib import Path\n"
            "running = []\n"
            "for path in Path('outputs').glob('*/job.json'):\n"
            "    try: job = json.loads(path.read_text())\n"
            "    except (OSError, json.JSONDecodeError): continue\n"
            "    if job.get('status') == 'RUNNING': running.append((job.get('started_at', ''), path, job))\n"
            "if len(running) < 2: raise SystemExit('Refusing metadata update: fewer than two RUNNING jobs found.')\n"
            "_, path, job = sorted(running)[-1]\n"
            "job['status'] = 'FAILED'\n"
            "job['completed_at'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')\n"
            "job['error_summary'] = 'Cancelled as the newer duplicate after interrupted recovery.'\n"
            "path.write_text(json.dumps(job, indent=2, sort_keys=True) + '\\n')\n"
            "print(json.dumps({'cancelled_duplicate_job_id': job['job_id']}))\n"
            "PY\n"
        ),
    },
    "docker_install": {
        "approval_required": True,
        "wsl_script": DOCKER_INSTALL_SCRIPT,
        "wsl_user": "root",
    },
}

CATALOG_PATH = Path(__file__).resolve().parent.parent / "t480" / "command-catalog.json"
CONFIGURATION_FINGERPRINT = fingerprint_files([TRANSPORT_CONFIG_PATH, CATALOG_PATH])


def validate_contract() -> None:
    """Refuse execution if the published contract and adapter have diverged."""
    validate_catalog(
        CATALOG_PATH,
        {operation_id: _shared_operation(operation_id, details) for operation_id, details in OPERATIONS.items()},
    )


def _shared_operation(operation_id: str, details: dict[str, Any]) -> Operation:
    return Operation(
        operation_id=operation_id,
        purpose=f"Execute the fixed AI Lab operation {operation_id}.",
        approval_required=bool(details["approval_required"]),
        powershell_command=details.get("command"),
        wsl_script=details.get("wsl_script"),
        wsl_user=details.get("wsl_user"),
        timeout_seconds=(
            TRANSPORT_SETTINGS.long_command_timeout_seconds
            if details["approval_required"]
            else TRANSPORT_SETTINGS.command_timeout_seconds
        ),
    )


def requirements() -> dict[str, Any]:
    return {
        "tool_id": TOOL_ID,
        "description": "Run fixed, audited T480 Windows/WSL operations over SSH.",
        "configuration_fingerprint": CONFIGURATION_FINGERPRINT,
        "requirements": [
            f"Set {SSH_TARGET_ENV}, or record it in the ignored {LOCAL_CONFIG_PATH.name} file.",
            "Configure SSH key authentication and verify the T480 host key before use.",
        "Ensure the Windows SSH account can run wsl.exe and access the Ubuntu distribution.",
        "Explicitly approve every mutating operation in the operator conversation before execution.",
    ],
        "commands": ["describe-requirements", "preflight", "healthcheck", "execute", "verify"],
        "operations": [
            {"id": operation_id, "approval_required": details["approval_required"]}
            for operation_id, details in OPERATIONS.items()
        ],
    }


def ssh_command(target: str, powershell_command: str) -> list[str]:
    """Run Windows OpenSSH from T16 PowerShell, not a separate WSL SSH config."""
    return build_ssh_command(target, powershell_command, TRANSPORT_SETTINGS)


def wsl_bash_script_command(script: str, user: str | None = None) -> str:
    """Send an exact UTF-8 script to WSL without CRLF or nested-script issues."""
    return build_wsl_powershell_command(script, TRANSPORT_SETTINGS, user)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def append_execution_log(command_name: str, operation_id: str | None, payload: dict[str, Any]) -> None:
    """Keep local audit metadata without retaining private host output."""
    append_shared_execution_log(
        EXECUTION_LOG_PATH,
        tool_id=TOOL_ID,
        command_name=command_name,
        operation_id=operation_id,
        payload=payload,
    )


def run_command(command: list[str]) -> dict[str, Any]:
    """Compatibility wrapper for explicitly approved large file transfers."""
    return run_shared_command(command, TRANSPORT_SETTINGS.long_command_timeout_seconds)


def configured_target() -> str:
    return resolve_ssh_target(TRANSPORT_SETTINGS, [LOCAL_CONFIG_PATH])


def preflight() -> dict[str, Any]:
    return shared_preflight(
        tool_id=TOOL_ID,
        settings=TRANSPORT_SETTINGS,
        config_paths=[LOCAL_CONFIG_PATH],
    )


def healthcheck_action(component: str, status: str) -> str:
    """Return safe guidance without embedding raw host output in the dashboard."""
    actions = {
        "control_path": "Check the T16 SSH target, host key, and T480 Windows/WSL availability.",
        "docker": "Run lab_runtime_diagnostics; do not restart Docker automatically.",
        "compose": "Review the deployed Compose configuration before making any change.",
        "postgres": "Run lab_runtime_diagnostics, then request approval before any recovery action.",
        "n8n": "Allow the startup grace period, then run lab_runtime_diagnostics if it remains unhealthy.",
        "health_dashboard": "Check the dashboard container and its local health endpoint; do not expose n8n instead.",
        "ollama": "Optional service: verify whether it was deliberately enabled before taking action.",
        "capacity": "Review disk or memory use before deploying, updating, or loading a model.",
    }
    if status == "PASS":
        return "No action required."
    if status == "SKIP":
        return "No action required while this optional service is intentionally disabled."
    return actions.get(component, "Run lab_runtime_diagnostics and review the failed check before taking action.")


def healthcheck_detail(component: str, status: str) -> str:
    """Keep the dashboard useful without copying raw command output to PostgreSQL."""
    details = {
        "docker": "Docker daemon reachability was checked.",
        "compose": "The deployed Compose configuration was checked.",
        "postgres": "PostgreSQL service readiness or query capability was checked.",
        "n8n": "The n8n service and its health endpoint were checked.",
        "health_dashboard": "The static health-dashboard service and endpoint were checked.",
        "ollama": "The optional Ollama service state was checked.",
        "capacity": "Available host disk or memory capacity was checked.",
        "revision": "The deployed checkout was compared with its fetched origin revision.",
        "image": "Configured service images were checked for immutable digest pinning.",
        "postgres_exposure": "PostgreSQL binding was checked against the loopback-only policy.",
        "n8n_exposure": "n8n binding was checked against the loopback-only policy.",
        "dashboard_exposure": "Dashboard binding was checked against the private-LAN policy.",
        "startup_task": "The Windows startup task was checked without changing it.",
        "dashboard_firewall": "The dashboard firewall rule was checked for private-LAN availability.",
        "vector": "A read-only pgvector expression was evaluated.",
    }
    if status == "SKIP":
        return "This optional service is intentionally not running."
    return details.get(component, "A fixed T480 health check was completed.")


def _lifecycle_metadata(detail: str) -> dict[str, Any]:
    """Extract only fixed lifecycle facts from health-check output."""
    match = re.search(r"started_at=([^\s]+)\s+restart_count=(\d+)", detail)
    if not match:
        return {}
    try:
        started_at = datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))
    except ValueError:
        return {"restart_count": int(match.group(2))}
    return {
        "observed_started_at": started_at.isoformat(),
        "observed_started_at_nz": started_at.astimezone(ZoneInfo("Pacific/Auckland")).isoformat(),
        "restart_count": int(match.group(2)),
    }


def _supplemental_check(operation: dict[str, Any], component: str, present_is_pass: bool = True) -> dict[str, Any]:
    """Create a redacted status check from a fixed JSON-returning operation."""
    result = operation.get("result", {})
    try:
        value = json.loads(str(result.get("stdout", "")))
    except json.JSONDecodeError:
        value = None
    if isinstance(value, list):
        value = value[0] if value else None
    valid = isinstance(value, dict) and bool(value.get("present", present_is_pass)) == present_is_pass
    status = "PASS" if operation.get("ok") and valid else "FAIL"
    return {
        "key": component,
        "status": status,
        "detail": healthcheck_detail(component, status),
        "recommended_action": healthcheck_action(component, status),
        "duration_ms": result.get("duration_ms"),
    }


def normalise_healthcheck(
    control_path: dict[str, Any], lab_health: dict[str, Any], supplemental: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Convert fixed health output into a small, dashboard-safe result payload."""
    control_result = control_path.get("remote_check", {})
    lab_result = lab_health.get("result", {})
    checks: list[dict[str, Any]] = [
        {
            "key": "control_path",
            "status": "PASS" if control_path.get("ok") else "FAIL",
            "detail": "T16 SSH, Windows PowerShell, and Ubuntu WSL round trip completed."
            if control_path.get("ok")
            else "The T16 could not complete the governed T480 control-path check.",
            "recommended_action": healthcheck_action("control_path", "PASS" if control_path.get("ok") else "FAIL"),
            "duration_ms": control_result.get("duration_ms"),
        }
    ]
    key_counts: dict[str, int] = {}
    for raw_line in str(lab_result.get("stdout", "")).splitlines():
        parts = raw_line.split(maxsplit=2)
        if len(parts) < 2 or parts[0] not in {"OK", "WARN", "FAIL", "SKIP"}:
            continue
        current_status = {"OK": "PASS", "WARN": "WARN", "FAIL": "FAIL", "SKIP": "SKIP"}[parts[0]]
        component = re.sub(r"[^a-z0-9_]+", "_", parts[1].lower()).strip("_") or "lab"
        key_counts[component] = key_counts.get(component, 0) + 1
        key = component if key_counts[component] == 1 else f"{component}_{key_counts[component]}"
        checks.append(
            {
                "key": key,
                "status": current_status,
                "detail": healthcheck_detail(component, current_status),
                "recommended_action": healthcheck_action(component, current_status),
                "duration_ms": None,
                **_lifecycle_metadata(parts[2] if len(parts) > 2 else ""),
            }
        )
    if not lab_health.get("ok") and not any(check["status"] == "FAIL" for check in checks):
        checks.append(
            {
                "key": "lab_health",
                "status": "FAIL",
                "detail": "The fixed T480 health operation did not complete successfully.",
                "recommended_action": "Run lab_runtime_diagnostics and review the failed check before taking action.",
                "duration_ms": lab_result.get("duration_ms"),
            }
        )
    for component, operation in (supplemental or {}).items():
        checks.append(_supplemental_check(operation, component))
    statuses = {check["status"] for check in checks}
    overall_status = "FAIL" if "FAIL" in statuses else "WARN" if "WARN" in statuses else "PASS"
    return {
        "started_at": control_result.get("started_at") or lab_result.get("started_at"),
        "started_at_nz": control_result.get("started_at_nz") or lab_result.get("started_at_nz"),
        "finished_at": lab_result.get("finished_at") or control_result.get("finished_at"),
        "finished_at_nz": lab_result.get("finished_at_nz") or control_result.get("finished_at_nz"),
        "overall_status": overall_status,
        "configuration_fingerprint": CONFIGURATION_FINGERPRINT,
        "checks": checks,
    }


def control_path_failure_summary(control_path: dict[str, Any]) -> dict[str, Any]:
    result = control_path.get("remote_check", {})
    return {
        "started_at": result.get("started_at"),
        "started_at_nz": result.get("started_at_nz"),
        "finished_at": result.get("finished_at"),
        "finished_at_nz": result.get("finished_at_nz"),
        "overall_status": "FAIL",
        "configuration_fingerprint": CONFIGURATION_FINGERPRINT,
        "checks": [
            {
                "key": "control_path",
                "status": "FAIL",
                "detail": "The T16 could not complete the governed T480 control-path check.",
                "recommended_action": healthcheck_action("control_path", "FAIL"),
                "duration_ms": result.get("duration_ms"),
            }
        ],
    }


def record_local_healthcheck(summary: dict[str, Any]) -> dict[str, int]:
    return append_health_history(
        summary,
        history_path=HEALTH_HISTORY_PATH,
        latest_path=HEALTH_LATEST_PATH,
        transitions_path=HEALTH_TRANSITIONS_PATH,
    )


def publish_healthcheck(summary: dict[str, Any]) -> dict[str, Any]:
    """Append a redacted health result and render the LAN status snapshot on the T480."""
    encoded_payload = base64.b64encode(json.dumps(summary, separators=(",", ":")).encode()).decode("ascii")
    if not re.fullmatch(r"[A-Za-z0-9+/=]+", encoded_payload):
        raise RuntimeError("Healthcheck summary could not be encoded safely.")
    script = f"""set -euo pipefail
cd /home/chris/projects/cs-ai-lab-infra
set -a
source .env
set +a
payload_b64='{encoded_payload}'
record_sql=\"SELECT monitoring.record_healthcheck(convert_from(decode(:'payload_b64', 'base64'), 'UTF8')::jsonb);\"
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -v payload_b64=\"$payload_b64\" -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" -c \"$record_sql\" </dev/null
dashboard_json=\"$(docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" -Atqc 'SELECT monitoring.health_dashboard_payload();' </dev/null)\"
printf '%s' \"$dashboard_json\" | python3 monitoring/dashboard/render_health_dashboard.py --output monitoring/dashboard/output/index.html
printf 'HEALTHCHECK_PUBLISHED=ok\\n'
"""
    operation = Operation(
        operation_id="healthcheck_publish",
        purpose="Append a redacted Healthcheck result and render the fixed LAN dashboard.",
        wsl_script=script,
        timeout_seconds=TRANSPORT_SETTINGS.command_timeout_seconds,
    )
    return execute_operation(
        operation,
        target=configured_target(),
        settings=TRANSPORT_SETTINGS,
        approved=False,
    )


def healthcheck() -> dict[str, Any]:
    """Run the fixed control-path and service-health checks, then publish a redacted result."""
    control_path = preflight()
    if not control_path["ok"]:
        summary = control_path_failure_summary(control_path)
        local_history = record_local_healthcheck(summary)
        return {
            "tool_id": TOOL_ID,
            "operation": "healthcheck",
            "approval_required": False,
            "approved": False,
            "checks": {"control_path": control_path},
            "summary": summary,
            "local_history": local_history,
            "ok": False,
        }
    lab_health = execute("lab_health", approved=False)
    supplemental = {
        "startup_task": execute("startup_status", approved=False),
        "dashboard_firewall": execute("health_dashboard_firewall_status", approved=False),
    }
    summary = normalise_healthcheck(control_path, lab_health, supplemental)
    published = publish_healthcheck(summary)
    if not published["ok"]:
        summary["checks"].append(
            {
                "key": "health_dashboard_persistence",
                "status": "FAIL",
                "detail": "The health result could not be saved to PostgreSQL and published to the dashboard.",
                "recommended_action": healthcheck_action("health_dashboard", "FAIL"),
                "duration_ms": published["result"].get("duration_ms"),
            }
        )
        summary["overall_status"] = "FAIL"
    local_history = record_local_healthcheck(summary)
    return {
        "tool_id": TOOL_ID,
        "operation": "healthcheck",
        "approval_required": False,
        "approved": False,
        "checks": {"control_path": control_path, "lab_health": lab_health, **supplemental, "dashboard_publish": published},
        "summary": summary,
        "local_history": local_history,
        "result": published["result"],
        "ok": lab_health["ok"] and published["ok"],
    }


def healthreport() -> dict[str, Any]:
    """Generate a redacted seven-day local report without contacting the T480."""
    report = weekly_report(HEALTH_HISTORY_PATH, HEALTH_WEEKLY_REPORT_PATH)
    return {
        "tool_id": TOOL_ID,
        "operation": "healthreport",
        "output": str(HEALTH_WEEKLY_REPORT_PATH),
        "report": report,
        "ok": True,
    }


def execute(operation_id: str, approved: bool) -> dict[str, Any]:
    details = OPERATIONS.get(operation_id)
    if details is None:
        raise RuntimeError(f"Unknown operation: {operation_id}")
    payload = execute_operation(
        _shared_operation(operation_id, details),
        target=configured_target(),
        settings=TRANSPORT_SETTINGS,
        approved=approved,
    )
    payload["tool_id"] = TOOL_ID
    return payload


def verify(operation_id: str) -> dict[str, Any]:
    verification_operation = "docker_status" if operation_id == "docker_install" else operation_id
    payload = execute(verification_operation, approved=False)
    payload["verified_operation"] = operation_id
    return payload


def local_path_from_windows_folder(value: str) -> Path:
    """Accept a Windows Explorer path when this adapter is called from WSL."""
    match = re.fullmatch(r"([A-Za-z]):[\\/](.*)", value)
    if match:
        return Path("/mnt") / match.group(1).lower() / match.group(2).replace("\\", "/")
    return Path(value)


def windows_path(value: Path) -> str:
    resolved = value.resolve()
    parts = resolved.parts
    if len(parts) >= 3 and parts[0] == "/" and parts[1] == "mnt" and len(parts[2]) == 1:
        return f"{parts[2].upper()}:\\" + "\\".join(parts[3:])
    raise ValueError("Source folder must be a Windows drive path (for example C:\\Users\\chris\\Videos).")


def powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upload_mp4(target: str, source: Path) -> dict[str, Any]:
    source_windows = windows_path(source)
    remote_destination = f"{target}:{TRANSCRIBER_WINDOWS_STAGING}/"
    command = (
        "$ErrorActionPreference = 'Stop'; "
        f"& scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- {powershell_quote(source_windows)} "
        f"{powershell_quote(remote_destination)}; "
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    )
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    return run_command(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded])


def stage_forex_m1_evidence(approved: bool) -> dict[str, Any]:
    """Transfer only the reviewed M1 capture, then hash-check it on the T480."""
    if not approved:
        raise PermissionError("stage-forex-m1-evidence requires --approve after explicit operator approval.")
    if not FOREX_M1_CAPTURE.is_file() or sha256_file(FOREX_M1_CAPTURE) != FOREX_M1_CAPTURE_SHA256:
        raise RuntimeError("The reviewed local Forex M1 capture is absent or has an unexpected hash.")
    source_windows = subprocess.run(
        ["wslpath", "-w", str(FOREX_M1_CAPTURE)], check=True, capture_output=True, text=True
    ).stdout.strip()
    destination = f"{configured_target()}:{FOREX_WINDOWS_STAGING}/capture.stdout.json"
    command = (
        "$ErrorActionPreference = 'Stop'; "
        f"& scp.exe -B -o BatchMode=yes -o StrictHostKeyChecking=yes -- {powershell_quote(source_windows)} {powershell_quote(destination)}; "
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    )
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    transfer = run_command(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded])
    if not transfer["ok"]:
        return {"tool_id": TOOL_ID, "operation": "forex_m1_evidence_stage", "approved": True, "transfer": transfer, "ok": False}
    staged = execute("forex_stage_m1_evidence", approved=True)
    return {"tool_id": TOOL_ID, "operation": "forex_m1_evidence_stage", "approved": True, "transfer": transfer, "stage": staged, "ok": staged["result"]["ok"]}


def submit_transcription_folder(source_folder: str, approved: bool) -> dict[str, Any]:
    """Serially submit direct MP4 files to the fixed private T480 inbox."""
    if not approved:
        raise PermissionError("submit-transcription-folder requires --approve after explicit operator approval.")
    folder = local_path_from_windows_folder(source_folder)
    if not folder.is_dir():
        raise RuntimeError(f"Source folder does not exist or is not a folder: {source_folder}")
    candidates = sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() == ".mp4")
    completed_result = execute("transcription_completed_hashes", approved=False)
    if not completed_result["result"]["ok"]:
        return {"tool_id": TOOL_ID, "operation": "transcription_folder_submission", "approval_required": True, "approved": True, "completed_hashes": completed_result, "files": [], "ok": False}
    completed_hashes = set(json.loads(completed_result["result"]["stdout"]))
    files = [path for path in candidates if sha256_file(path) not in completed_hashes]
    if not files:
        return {"tool_id": TOOL_ID, "operation": "transcription_folder_submission", "approval_required": True, "approved": True, "files": [], "skipped_completed": len(candidates), "ok": True}
    unsafe = [path.name for path in files if not PORTABLE_MP4_NAME.fullmatch(path.name)]
    if unsafe:
        raise RuntimeError("Rename MP4 files to use only letters, numbers, spaces, dots, underscores, and hyphens: " + ", ".join(unsafe))

    prepared = execute("transcription_prepare", approved=True)
    if not prepared["result"]["ok"]:
        return {"tool_id": TOOL_ID, "operation": "transcription_folder_submission", "approval_required": True, "approved": True, "prepare": prepared, "files": [], "ok": False}
    staging = execute("transcription_windows_staging_prepare", approved=True)
    if not staging["result"]["ok"]:
        return {"tool_id": TOOL_ID, "operation": "transcription_folder_submission", "approval_required": True, "approved": True, "staging": staging, "files": [], "ok": False}
    preflight_result = execute("transcription_preflight", approved=False)
    if not preflight_result["result"]["ok"]:
        return {"tool_id": TOOL_ID, "operation": "transcription_folder_submission", "approval_required": True, "approved": True, "preflight": preflight_result, "files": [], "ok": False}
    if "incoming_count=0" not in preflight_result["result"]["stdout"]:
        cleanup = execute("transcription_cleanup_completed_inbox", approved=True)
        if not cleanup["result"]["ok"]:
            return {"tool_id": TOOL_ID, "operation": "transcription_folder_submission", "approval_required": True, "approved": True, "cleanup": cleanup, "files": [], "ok": False}
        preflight_result = execute("transcription_preflight", approved=False)
        if "incoming_count=0" not in preflight_result["result"]["stdout"]:
            raise RuntimeError("T480 transcription inbox still contains an unfinished prior job; resolve it before submitting another folder.")

    processed: list[dict[str, Any]] = []
    target = configured_target()
    for source in files:
        transfer = upload_mp4(target, source)
        entry: dict[str, Any] = {"filename": source.name, "transfer": transfer}
        if not transfer["ok"]:
            processed.append(entry)
            return {"tool_id": TOOL_ID, "operation": "transcription_folder_submission", "approval_required": True, "approved": True, "files": processed, "ok": False}
        run = execute("transcription_process_next", approved=True)
        entry["transcription"] = run
        processed.append(entry)
        if not run["result"]["ok"]:
            return {"tool_id": TOOL_ID, "operation": "transcription_folder_submission", "approval_required": True, "approved": True, "files": processed, "ok": False}
    return {"tool_id": TOOL_ID, "operation": "transcription_folder_submission", "approval_required": True, "approved": True, "files": processed, "skipped_completed": len(candidates) - len(files), "ok": True}


def pull_transcription_outputs(approved: bool) -> dict[str, Any]:
    """Copy only completed review artefacts to the fixed local Windows folder."""
    if not approved:
        raise PermissionError("pull-transcription-outputs requires --approve after explicit operator approval.")
    prepared = execute("transcription_export_prepare", approved=True)
    if not prepared["result"]["ok"]:
        return {"tool_id": TOOL_ID, "operation": "transcription_output_pull", "approval_required": True, "approved": True, "prepare": prepared, "ok": False}
    destination_windows = windows_path(TRANSCRIBER_LOCAL_EXPORT)
    remote_source = f"{configured_target()}:{TRANSCRIBER_WINDOWS_EXPORT}/."
    command = (
        "$ErrorActionPreference = 'Stop'; "
        f"New-Item -ItemType Directory -Force -Path {powershell_quote(destination_windows)} | Out-Null; "
        f"& scp.exe -B -r -o BatchMode=yes -o StrictHostKeyChecking=yes -- {powershell_quote(remote_source)} {powershell_quote(destination_windows)}; "
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    )
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    transfer = run_command(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded])
    organization = organize_local_transcription_exports() if transfer["ok"] else None
    return {"tool_id": TOOL_ID, "operation": "transcription_output_pull", "approval_required": True, "approved": True, "prepare": prepared, "transfer": transfer, "organization": organization, "destination": str(TRANSCRIBER_LOCAL_EXPORT), "ok": transfer["ok"] and organization["ok"]}


def organize_local_transcription_exports() -> dict[str, Any]:
    """Replace opaque historic job-id folders with safely-derived source names."""
    root = TRANSCRIBER_LOCAL_EXPORT
    root.mkdir(parents=True, exist_ok=True)
    migrated: list[dict[str, str]] = []
    collisions: list[str] = []
    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        metadata_path = folder / "job.json"
        if not metadata_path.is_file():
            continue
        try:
            job = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        source_stem = Path(str(job.get("input_filename", ""))).stem
        if not source_stem or Path(source_stem).name != source_stem or folder.name == source_stem:
            continue
        destination = root / source_stem
        if destination.exists():
            destination_metadata = destination / "job.json"
            try:
                same_job = json.loads(destination_metadata.read_text(encoding="utf-8")).get("job_id") == job.get("job_id")
            except (OSError, json.JSONDecodeError):
                same_job = False
            if not same_job:
                collisions.append(folder.name)
                continue
            shutil.rmtree(folder)
            migrated.append({"removed_duplicate_job_id_folder": folder.name, "source_folder": source_stem})
            continue
        folder.rename(destination)
        migrated.append({"renamed_job_id_folder": folder.name, "source_folder": source_stem})
    return {"ok": not collisions, "migrated": migrated, "collisions": collisions}


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description="Governed SSH/WSL adapter for the T480 AI Lab.")
    command_parser.add_argument(
        "command",
        type=str.lower,
        choices=["describe-requirements", "preflight", "healthcheck", "healthreport", "execute", "verify", "submit-transcription-folder", "pull-transcription-outputs", "stage-forex-m1-evidence"],
    )
    command_parser.add_argument("--operation", choices=sorted(OPERATIONS), help="Fixed operation identifier.")
    command_parser.add_argument("--source-folder", help="Windows Explorer folder containing direct MP4 files; accepted only by submit-transcription-folder.")
    command_parser.add_argument("--approve", action="store_true", help="Record explicit approval for a mutating operation.")
    return command_parser


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    validate_contract()
    if args.command == "describe-requirements":
        payload = requirements()
    elif args.command == "preflight":
        payload = preflight()
    elif args.command == "healthcheck":
        payload = healthcheck()
    elif args.command == "healthreport":
        payload = healthreport()
    elif args.command == "submit-transcription-folder":
        if not args.source_folder:
            raise SystemExit("--source-folder is required for submit-transcription-folder")
        payload = submit_transcription_folder(args.source_folder, args.approve)
    elif args.command == "pull-transcription-outputs":
        payload = pull_transcription_outputs(args.approve)
    elif args.command == "stage-forex-m1-evidence":
        payload = stage_forex_m1_evidence(args.approve)
    else:
        if not args.operation:
            raise SystemExit("--operation is required for execute and verify")
        payload = execute(args.operation, args.approve) if args.command == "execute" else verify(args.operation)
    payload["configuration_fingerprint"] = CONFIGURATION_FINGERPRINT
    append_execution_log(args.command, args.operation, payload)
    print(json.dumps(payload, indent=2))
    if args.command == "describe-requirements":
        return 0
    return 0 if payload.get("ok", payload.get("result", {}).get("ok", False)) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PermissionError, RuntimeError, ValueError) as error:
        print(json.dumps({"tool_id": TOOL_ID, "ok": False, "error": str(error)}, indent=2), file=sys.stderr)
        raise SystemExit(2)
