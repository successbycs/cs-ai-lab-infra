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
import gzip
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
FOREX_REVISION = "62ca5836ba49aad85111e247eaebec25ef185ce8"
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
    "tailscale_windows_status": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$exe = Join-Path $env:ProgramFiles 'Tailscale\\tailscale.exe'; "
            "$service = Get-CimInstance Win32_Service -Filter \"Name='Tailscale'\" -ErrorAction SilentlyContinue | Select-Object Name,State,StartMode,StartName; "
            "$version = if (Test-Path -LiteralPath $exe -PathType Leaf) { (& $exe version 2>$null | Select-Object -First 1) } else { $null }; "
            "$backend = if (Test-Path -LiteralPath $exe -PathType Leaf) { (& $exe status --json 2>$null | ConvertFrom-Json -ErrorAction SilentlyContinue | Select-Object BackendState,Self) } else { $null }; "
            "[pscustomobject]@{ installed = [bool](Test-Path -LiteralPath $exe -PathType Leaf); version = $version; service = $service; backend = $backend } | ConvertTo-Json -Depth 5 -Compress"
        ),
    },
    "tailscale_tailnet_peers": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; $exe = Join-Path $env:ProgramFiles 'Tailscale\\tailscale.exe'; "
            "if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Tailscale is not installed.' }; "
            "$status = & $exe status --json | ConvertFrom-Json; "
            "$peers = @($status.Peer.PSObject.Properties | ForEach-Object { $peer = $_.Value; [pscustomobject]@{ host_name = $peer.HostName; os = $peer.OS; online = $peer.Online; active = $peer.Active; exit_node = $peer.ExitNode; allowed_ips = $peer.AllowedIPs } }); "
            "[pscustomobject]@{ backend_state = $status.BackendState; self_online = $status.Self.Online; self_exit_node = $status.Self.ExitNode; peer_count = $peers.Count; peers = $peers } | ConvertTo-Json -Depth 5 -Compress"
        ),
    },
    "tailscale_windows_install": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue'; "
            "$uri = 'https://dl.tailscale.com/stable/tailscale-setup-1.102.3-amd64.msi'; "
            "$destinationDir = Join-Path $env:ProgramData 'CSAILab\\installers'; $destination = Join-Path $destinationDir 'tailscale-setup-1.102.3-amd64.msi'; "
            "New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null; "
            "Invoke-WebRequest -Uri $uri -OutFile $destination -UseBasicParsing; "
            "$signature = Get-AuthenticodeSignature -FilePath $destination; "
            "if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Tailscale') { throw 'Downloaded Tailscale installer signature validation failed.' }; "
            "$install = Start-Process -FilePath 'msiexec.exe' -ArgumentList @('/i', $destination, '/qn', 'TS_NOLAUNCH=1') -Wait -PassThru; "
            "if ($install.ExitCode -notin @(0,3010)) { throw \"Tailscale MSI installation failed with exit code $($install.ExitCode).\" }; "
            "$exe = Join-Path $env:ProgramFiles 'Tailscale\\tailscale.exe'; if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Tailscale executable was absent after MSI installation.' }; "
            "$service = Get-CimInstance Win32_Service -Filter \"Name='Tailscale'\" -ErrorAction Stop | Select-Object Name,State,StartMode; "
            "[pscustomobject]@{ installed = $true; installer_version = '1.102.3'; installer_signature = $signature.Status.ToString(); installer_signer = $signature.SignerCertificate.Subject; msi_exit_code = $install.ExitCode; client_version = (& $exe version 2>$null | Select-Object -First 1); service = $service; login_required = $true; next_action = 'Sign in locally to Tailscale with the owner account; do not enable routes, exit node, or public exposure.' } | ConvertTo-Json -Depth 5 -Compress"
        ),
    },
    "performance_diagnostics": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$os = Get-CimInstance Win32_OperatingSystem; $cpu = Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average; "
            "$memoryTotal = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2); $memoryFree = [math]::Round($os.FreePhysicalMemory / 1MB, 2); "
            "$disks = @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType = 3' | Select-Object DeviceID,@{Name='free_gib';Expression={[math]::Round($_.FreeSpace / 1GB,2)}},@{Name='free_percent';Expression={[math]::Round(100*$_.FreeSpace/$_.Size,1)}}); "
            "$processes = @(Get-Process -ErrorAction SilentlyContinue | Sort-Object CPU -Descending | Select-Object -First 20 ProcessName,Id,@{Name='cpu_seconds';Expression={[math]::Round($_.CPU,1)}},@{Name='working_set_mib';Expression={[math]::Round($_.WorkingSet64 / 1MB,1)}},Responding,StartTime); "
            "$rdpService = Get-CimInstance Win32_Service -Filter \"Name='TermService'\" | Select-Object Name,State,StartMode,ProcessId; "
            "$rdpSessions = @(Get-CimInstance Win32_LogonSession -Filter 'LogonType = 10' -ErrorAction SilentlyContinue | Select-Object LogonId,StartTime,AuthenticationPackage); "
            "$rdpListeners = @(Get-NetTCPConnection -LocalPort 3389 -ErrorAction SilentlyContinue | Select-Object State,LocalAddress,LocalPort,RemoteAddress,RemotePort,OwningProcess); "
            "$network = @(Get-CimInstance Win32_PerfFormattedData_Tcpip_NetworkInterface -ErrorAction SilentlyContinue | Select-Object Name,BytesReceivedPersec,BytesSentPersec,OutputQueueLength | Sort-Object BytesSentPersec -Descending | Select-Object -First 10); "
            "[pscustomobject]@{ captured_at_utc = (Get-Date).ToUniversalTime().ToString('o'); uptime_since_utc = $os.LastBootUpTime.ToUniversalTime().ToString('o'); cpu_load_percent = [math]::Round($cpu.Average,1); memory_total_gib = $memoryTotal; memory_free_gib = $memoryFree; memory_used_percent = [math]::Round(100 * (1 - $memoryFree / $memoryTotal),1); disks = $disks; top_processes_by_cpu_seconds = $processes; rdp_service = $rdpService; rdp_network_logon_sessions = $rdpSessions; rdp_tcp_connections = $rdpListeners; network_interfaces = $network } | ConvertTo-Json -Depth 6 -Compress"
        ),
    },
    "security_windows_baseline": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$os = Get-CimInstance Win32_OperatingSystem; "
            "$ubr = (Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion' -ErrorAction SilentlyContinue).UBR; "
            "$latestHotfix = Get-HotFix -ErrorAction SilentlyContinue | Sort-Object InstalledOn -Descending | Select-Object -First 1 HotFixID,InstalledOn,Description; "
            "$firewall = try { @(Get-NetFirewallProfile -ErrorAction Stop | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction,NotifyOnListen,AllowInboundRules,AllowLocalFirewallRules) } catch { @([pscustomobject]@{ error = $_.Exception.Message }) }; "
            "$bitlocker = try { @(Get-BitLockerVolume | Select-Object MountPoint,VolumeType,ProtectionStatus,VolumeStatus,EncryptionMethod,EncryptionPercentage,AutoUnlockEnabled) } catch { @([pscustomobject]@{ error = $_.Exception.Message }) }; "
            "$secureBoot = try { [bool](Confirm-SecureBootUEFI) } catch { $null }; "
            "$deviceGuard = try { Get-CimInstance -Namespace root/Microsoft/Windows/DeviceGuard -ClassName Win32_DeviceGuard | Select-Object SecurityServicesConfigured,SecurityServicesRunning,VirtualizationBasedSecurityStatus,CodeIntegrityPolicyEnforcementStatus,UsermodeCodeIntegrityPolicyEnforcementStatus } catch { [pscustomobject]@{ error = $_.Exception.Message } }; "
            "$uac = Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System' -ErrorAction SilentlyContinue | Select-Object EnableLUA,ConsentPromptBehaviorAdmin,PromptOnSecureDesktop,FilterAdministratorToken,LocalAccountTokenFilterPolicy; "
            "$smartScreen = Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer' -ErrorAction SilentlyContinue | Select-Object SmartScreenEnabled; "
            "$rdp = Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server' -ErrorAction SilentlyContinue | Select-Object fDenyTSConnections; "
            "$smb = try { Get-SmbServerConfiguration | Select-Object EnableSMB1Protocol,EnableSMB2Protocol,EncryptData,RejectUnencryptedAccess,RequireSecuritySignature,EnableSecuritySignature } catch { [pscustomobject]@{ error = $_.Exception.Message } }; "
            "[pscustomobject]@{ os = [pscustomobject]@{ caption = $os.Caption; version = $os.Version; build = $os.BuildNumber; ubr = $ubr; architecture = $os.OSArchitecture; install_date = $os.InstallDate; last_boot = $os.LastBootUpTime }; latest_hotfix = $latestHotfix; firewall_profiles = $firewall; bitlocker = $bitlocker; secure_boot = $secureBoot; device_guard = $deviceGuard; uac = $uac; smart_screen = $smartScreen; rdp = $rdp; smb_server = $smb } | ConvertTo-Json -Depth 8 -Compress"
        ),
    },
    "security_defender_status": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$mp = try { $s = Get-MpComputerStatus; $p = Get-MpPreference; [pscustomobject]@{ status = $s | Select-Object AMServiceEnabled,AntivirusEnabled,AntispywareEnabled,BehaviorMonitorEnabled,IoavProtectionEnabled,NISEnabled,OnAccessProtectionEnabled,RealTimeProtectionEnabled,IsTamperProtected,DefenderSignaturesOutOfDate,AntivirusSignatureVersion,AntivirusSignatureLastUpdated,AntispywareSignatureVersion,AntispywareSignatureLastUpdated,QuickScanAge,QuickScanEndTime,FullScanAge,FullScanEndTime,RebootRequired; preferences = $p | Select-Object DisableArchiveScanning,DisableBehaviorMonitoring,DisableBlockAtFirstSeen,DisableEmailScanning,DisableIOAVProtection,DisableRealtimeMonitoring,DisableRemovableDriveScanning,DisableScanningMappedNetworkDrivesForFullScan,DisableScanningNetworkFiles,PUAProtection,MAPSReporting,SubmitSamplesConsent,CloudBlockLevel,EnableControlledFolderAccess,ExclusionPath,ExclusionExtension,ExclusionProcess,AttackSurfaceReductionRules_Ids,AttackSurfaceReductionRules_Actions } } catch { [pscustomobject]@{ error = $_.Exception.Message } }; "
            "$detections = try { @(Get-MpThreatDetection -ErrorAction Stop | Sort-Object InitialDetectionTime -Descending | Select-Object -First 50 ThreatID,ThreatStatusID,ActionSuccess,InitialDetectionTime,LastThreatStatusChangeTime,Resources) } catch { @([pscustomobject]@{ error = $_.Exception.Message }) }; "
            "$av = try { @(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct -ErrorAction Stop | Select-Object displayName,productState,pathToSignedProductExe,pathToSignedReportingExe) } catch { @([pscustomobject]@{ error = $_.Exception.Message }) }; "
            "[pscustomobject]@{ defender = $mp; defender_detections = $detections; registered_antivirus = $av } | ConvertTo-Json -Depth 7 -Compress"
        ),
    },
    "security_accounts_and_shares": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$users = try { @(Get-LocalUser | Select-Object Name,Enabled,LastLogon,PasswordRequired,PasswordExpires,UserMayChangePassword,PasswordLastSet,PrincipalSource) } catch { @([pscustomobject]@{ error = $_.Exception.Message }) }; "
            "$administrators = try { @(Get-LocalGroupMember -Group 'Administrators' | Select-Object Name,ObjectClass,PrincipalSource) } catch { @([pscustomobject]@{ error = $_.Exception.Message }) }; "
            "$remoteDesktopUsers = try { @(Get-LocalGroupMember -Group 'Remote Desktop Users' | Select-Object Name,ObjectClass,PrincipalSource) } catch { @([pscustomobject]@{ error = $_.Exception.Message }) }; "
            "$autologon = Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon' -ErrorAction SilentlyContinue | Select-Object AutoAdminLogon,DefaultUserName,DefaultDomainName,ForceAutoLogon; "
            "$shares = try { @(Get-SmbShare | Select-Object Name,Path,Description,Special,EncryptData,FolderEnumerationMode) } catch { @([pscustomobject]@{ error = $_.Exception.Message }) }; "
            "$passwordPolicy = (& net.exe accounts | Out-String); "
            "[pscustomobject]@{ current_identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name; elevated_administrator = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator); local_users = $users; administrators = $administrators; remote_desktop_users = $remoteDesktopUsers; autologon = $autologon; smb_shares = $shares; password_policy = $passwordPolicy } | ConvertTo-Json -Depth 6 -Compress"
        ),
    },
    "security_network_exposure": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue'; "
            "$processCache = @{}; function Process-Fact([int]$processId) { if (-not $processCache.ContainsKey($processId)) { $p = Get-Process -Id $processId -ErrorAction SilentlyContinue; $path = $p.Path; $sig = if ($path) { (Get-AuthenticodeSignature -FilePath $path -ErrorAction SilentlyContinue).Status.ToString() } else { $null }; $processCache[$processId] = [pscustomobject]@{ name = $p.ProcessName; path = $path; signature = $sig } }; return $processCache[$processId] }; "
            "$tcpRaw = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Sort-Object LocalPort,LocalAddress); $tcp = @($tcpRaw | Select-Object -First 100 | ForEach-Object { $p = Process-Fact $_.OwningProcess; [pscustomobject]@{ address = $_.LocalAddress; port = $_.LocalPort; pid = $_.OwningProcess; process = $p.name; path = $p.path; signature = $p.signature } }); "
            "$udpRaw = @(Get-NetUDPEndpoint -ErrorAction SilentlyContinue | Sort-Object LocalPort,LocalAddress); $udp = @($udpRaw | Select-Object -First 100 | ForEach-Object { $p = Process-Fact $_.OwningProcess; [pscustomobject]@{ address = $_.LocalAddress; port = $_.LocalPort; pid = $_.OwningProcess; process = $p.name; path = $p.path; signature = $p.signature } }); "
            "$ruleError = $null; $rules = try { @(Get-NetFirewallRule -Enabled True -Direction Inbound -Action Allow -ErrorAction Stop) } catch { $ruleError = $_.Exception.Message; @() }; "
            "$inbound = @($rules | ForEach-Object { $rule = $_; $ports = @($rule | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue); foreach ($port in $ports) { if ($port.LocalPort -ne 'Any' -or $rule.Profile.ToString() -match 'Public|Any') { [pscustomobject]@{ display_name = $rule.DisplayName; profile = $rule.Profile.ToString(); protocol = $port.Protocol.ToString(); local_port = $port.LocalPort } } } } | Sort-Object profile,local_port,display_name | Select-Object -First 60); "
            "$portProxy = (& netsh.exe interface portproxy show all | Out-String); "
            "$profiles = try { @(Get-NetConnectionProfile -ErrorAction Stop | Select-Object Name,InterfaceAlias,NetworkCategory,IPv4Connectivity,IPv6Connectivity) } catch { @([pscustomobject]@{ error = $_.Exception.Message }) }; "
            "[pscustomobject]@{ connection_profiles = $profiles; tcp_listener_count = $tcpRaw.Count; tcp_listeners = $tcp; udp_endpoint_count = $udpRaw.Count; udp_endpoints = $udp; listener_result_limit = 100; enabled_inbound_allow_rule_count = $rules.Count; reviewed_inbound_allow_rules = $inbound; inbound_rule_error = $ruleError; inbound_rule_result_limit = 60; port_proxy = $portProxy } | ConvertTo-Json -Depth 6 -Compress"
        ),
    },
    "security_sensitive_firewall_rules": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue'; "
            "$targets = @('22','139','445','3389','5432','8080'); $matches = @(); "
            "$rules = Get-NetFirewallRule -Enabled True -Direction Inbound -Action Allow -ErrorAction SilentlyContinue; "
            "foreach ($rule in $rules) { foreach ($port in @($rule | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue)) { if ($targets -contains [string]$port.LocalPort) { $address = $rule | Get-NetFirewallAddressFilter -ErrorAction SilentlyContinue; $matches += [pscustomobject]@{ display_name = $rule.DisplayName; profile = $rule.Profile.ToString(); protocol = $port.Protocol.ToString(); local_port = $port.LocalPort; remote_address = $address.RemoteAddress } } } }; "
            "[pscustomobject]@{ sensitive_ports = $targets; enabled_inbound_allow_rules = @($matches | Sort-Object local_port,profile,display_name) } | ConvertTo-Json -Depth 5 -Compress"
        ),
    },
    "security_remote_access": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$rdp = Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp' -ErrorAction SilentlyContinue | Select-Object UserAuthentication,SecurityLayer,MinEncryptionLevel; "
            "$sshd = Get-CimInstance Win32_Service -Filter \"Name='sshd'\" -ErrorAction SilentlyContinue | Select-Object Name,State,StartMode,StartName,PathName; "
            "$sshdExe = Join-Path $env:WINDIR 'System32\\OpenSSH\\sshd.exe'; $effective = if (Test-Path -LiteralPath $sshdExe -PathType Leaf) { & $sshdExe -T 2>$null } else { @('sshd_executable_absent') }; $sshDirectives = @($effective | Where-Object { $_ -match '^(passwordauthentication|pubkeyauthentication|authenticationmethods|permitrootlogin|permitemptypasswords|maxauthtries)\\s' } | ForEach-Object { [string]$_ }); "
            "$winrm = Get-CimInstance Win32_Service -Filter \"Name='WinRM'\" -ErrorAction SilentlyContinue | Select-Object Name,State,StartMode,StartName; "
            "[pscustomobject]@{ rdp_tcp = $rdp; openssh_service = $sshd; openssh_security_directives = $sshDirectives; winrm_service = $winrm } | ConvertTo-Json -Depth 5 -Compress"
        ),
    },
    "rdp_session_diagnostics": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$sessions = (quser.exe 2>&1 | Out-String).Trim(); "
            "$names = @('explorer','winlogon','dwm','LogonUI','userinit','ShellExperienceHost','StartMenuExperienceHost'); "
            "$shell = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $names -contains $_.ProcessName } | Select-Object ProcessName,Id,SessionId,Responding,@{Name='working_set_mib';Expression={[math]::Round($_.WorkingSet64/1MB,1)}},@{Name='cpu_seconds';Expression={if ($null -eq $_.CPU) {$null} else {[math]::Round($_.CPU,1)}}}); "
            "$events = @(Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-TerminalServices-LocalSessionManager/Operational'; StartTime=(Get-Date).AddHours(-2)} -ErrorAction SilentlyContinue | Select-Object -First 30 TimeCreated,Id,LevelDisplayName | ForEach-Object {[pscustomobject]@{time_utc=$_.TimeCreated.ToUniversalTime().ToString('o');id=$_.Id;level=$_.LevelDisplayName}}); "
            "$profiles = @(Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='Microsoft-Windows-User Profiles Service'; StartTime=(Get-Date).AddHours(-2)} -ErrorAction SilentlyContinue | Select-Object -First 20 TimeCreated,Id,LevelDisplayName,Message | ForEach-Object {[pscustomobject]@{time_utc=$_.TimeCreated.ToUniversalTime().ToString('o');id=$_.Id;level=$_.LevelDisplayName;message=$_.Message}}); "
            "$services = @(Get-Service -Name 'ProfSvc','AppReadiness','TermService' -ErrorAction SilentlyContinue | Select-Object Name,Status,StartType); "
            "[pscustomobject]@{rdp_sessions=$sessions;shell_processes=$shell;recent_terminal_session_events=$events;recent_profile_events=$profiles;session_services=$services}|ConvertTo-Json -Depth 5 -Compress"
        ),
    },
    "rdp_app_readiness_start": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$service=Get-Service -Name 'AppReadiness' -ErrorAction Stop; "
            "if($service.Status -ne 'Running'){Start-Service -Name 'AppReadiness' -ErrorAction Stop}; "
            "Start-Sleep -Seconds 2; $service=Get-Service -Name 'AppReadiness' -ErrorAction Stop; "
            "[pscustomobject]@{service=$service.Name;status=$service.Status.ToString();action='START_ONLY'}|ConvertTo-Json -Compress"
        ),
    },
    "security_persistence": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$startup = @(Get-CimInstance Win32_StartupCommand -ErrorAction SilentlyContinue | Select-Object Name,Command,Location,User); "
            "$runKeys = @(); foreach ($key in @('HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run','HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\RunOnce','HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Run','HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run','HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\RunOnce')) { if (Test-Path $key) { $item = Get-ItemProperty $key; foreach ($property in $item.PSObject.Properties | Where-Object Name -NotMatch '^PS') { $runKeys += [pscustomobject]@{ key = $key; name = $property.Name; command = [string]$property.Value } } } }; "
            "$tasks = try { @(Get-ScheduledTask -ErrorAction Stop | Where-Object TaskPath -NotLike '\\Microsoft\\*' | ForEach-Object { $task = $_; foreach ($action in @($task.Actions)) { [pscustomobject]@{ task_name = $task.TaskName; task_path = $task.TaskPath; state = $task.State.ToString(); enabled = $task.Settings.Enabled; principal = $task.Principal.UserId; run_level = $task.Principal.RunLevel.ToString(); execute = $action.Execute; arguments = $action.Arguments } } }) } catch { @([pscustomobject]@{ error = $_.Exception.Message }) }; "
            "[pscustomobject]@{ startup_commands = $startup; run_keys = $runKeys; non_microsoft_scheduled_tasks = $tasks } | ConvertTo-Json -Depth 7 -Compress"
        ),
    },
    "security_persistence_signatures": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; function Inspect-Command([string]$source,[string]$name,[string]$command) { if (-not $command) { return }; $raw = [Environment]::ExpandEnvironmentVariables($command.Trim()); $quoted = $raw.StartsWith([string][char]34); $start = if ($quoted) { 1 } else { 0 }; $end = $raw.IndexOf('.exe',[StringComparison]::OrdinalIgnoreCase); if ($end -lt 0) { return [pscustomobject]@{ source=$source; name=$name; command=$command; executable=$null; present=$false; signature='NotExecutable' } }; $exe = $raw.Substring($start,$end + 4 - $start); $present = Test-Path -LiteralPath $exe -PathType Leaf; $sig = if ($present) { (Get-AuthenticodeSignature -FilePath $exe -ErrorAction SilentlyContinue).Status.ToString() } else { 'PathNotResolved' }; [pscustomobject]@{ source=$source; name=$name; command=$command; executable=$exe; present=$present; signature=$sig } }; "
            "$items = @(); foreach ($entry in @(Get-CimInstance Win32_StartupCommand -ErrorAction SilentlyContinue)) { $items += Inspect-Command 'startup' $entry.Name $entry.Command }; foreach ($task in @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object TaskPath -NotLike '\\Microsoft\\*')) { foreach ($action in @($task.Actions)) { $items += Inspect-Command 'scheduled_task' ($task.TaskPath + $task.TaskName) $action.Execute } }; "
            "[pscustomobject]@{ inspected = @($items | Where-Object { $_ }); inspected_count = @($items | Where-Object { $_ }).Count } | ConvertTo-Json -Depth 5 -Compress"
        ),
    },
    "security_services": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$services = try { @(Get-CimInstance Win32_Service -ErrorAction Stop | Where-Object { $_.StartMode -eq 'Auto' -and $_.PathName } | ForEach-Object { $raw = [Environment]::ExpandEnvironmentVariables($_.PathName); $quoted = $raw.StartsWith([string][char]34); $start = if ($quoted) { 1 } else { 0 }; $end = $raw.IndexOf('.exe',[StringComparison]::OrdinalIgnoreCase); $exe = if ($end -ge 0) { $raw.Substring($start,$end + 4 - $start) } else { $raw }; $sig = if (Test-Path -LiteralPath $exe -PathType Leaf) { (Get-AuthenticodeSignature -FilePath $exe -ErrorAction SilentlyContinue).Status.ToString() } else { 'PathNotResolved' }; [pscustomobject]@{ name = $_.Name; display_name = $_.DisplayName; state = $_.State; start_name = $_.StartName; path_name = $raw; executable = $exe; signature = $sig; unquoted_space_path = (-not $quoted -and $exe.Contains(' ')) } }) } catch { @([pscustomobject]@{ error = $_.Exception.Message }) }; "
            "[pscustomobject]@{ automatic_services = $services } | ConvertTo-Json -Depth 5 -Compress"
        ),
    },
    "security_wmi_powershell": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$wmi = try { $filters = @(Get-CimInstance -Namespace root/subscription -ClassName __EventFilter -ErrorAction Stop | Select-Object Name,Query,EventNamespace); $consumers = @(Get-CimInstance -Namespace root/subscription -ClassName __EventConsumer | Select-Object @{Name='class';Expression={$_.CimClass.CimClassName}},Name); $bindings = @(Get-CimInstance -Namespace root/subscription -ClassName __FilterToConsumerBinding | Select-Object Filter,Consumer); [pscustomobject]@{ filters = $filters; consumers = $consumers; bindings = $bindings } } catch { [pscustomobject]@{ error = $_.Exception.Message } }; "
            "$profileFiles = @($PROFILE.AllUsersAllHosts,$PROFILE.AllUsersCurrentHost,$PROFILE.CurrentUserAllHosts,$PROFILE.CurrentUserCurrentHost) | Sort-Object -Unique | ForEach-Object { if (Test-Path -LiteralPath $_ -PathType Leaf) { Get-Item -LiteralPath $_ | Select-Object FullName,Length,LastWriteTime } }; "
            "$policy = Get-ExecutionPolicy -List | ForEach-Object { [pscustomobject]@{ scope = $_.Scope.ToString(); execution_policy = $_.ExecutionPolicy.ToString() } }; "
            "[pscustomobject]@{ permanent_wmi_subscriptions = $wmi; powershell_profile_files = @($profileFiles); powershell_language_mode = $ExecutionContext.SessionState.LanguageMode.ToString(); execution_policy = @($policy) } | ConvertTo-Json -Depth 6 -Compress"
        ),
    },
    "security_software_inventory": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$programs = @(); foreach ($key in @('HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*','HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*','HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*')) { $programs += Get-ItemProperty $key -ErrorAction SilentlyContinue | Where-Object DisplayName | Select-Object DisplayName,DisplayVersion,Publisher,InstallDate,InstallLocation,UninstallString }; $programs = @($programs | Sort-Object DisplayName,DisplayVersion -Unique); "
            "$appx = try { @(Get-AppxPackage | Where-Object { -not $_.IsFramework } | Select-Object Name,Version,Publisher,SignatureKind,Architecture,IsDevelopmentMode,NonRemovable) } catch { @([pscustomobject]@{ error = $_.Exception.Message }) }; "
            "$unsignedDrivers = @(Get-CimInstance Win32_PnPSignedDriver -ErrorAction SilentlyContinue | Where-Object { $_.IsSigned -ne $true } | Select-Object DeviceName,DriverProviderName,DriverVersion,DriverDate,InfName,IsSigned); "
            "$hotfixes = @(Get-HotFix -ErrorAction SilentlyContinue | Sort-Object InstalledOn -Descending | Select-Object -First 30 HotFixID,Description,InstalledOn,InstalledBy); "
            "$features = try { @(Get-WindowsOptionalFeature -Online -ErrorAction Stop | Where-Object State -eq 'Enabled' | Select-Object FeatureName,State) } catch { @([pscustomobject]@{ error = $_.Exception.Message }) }; "
            "[pscustomobject]@{ installed_programs = $programs; appx_packages = $appx; unsigned_pnp_drivers = $unsignedDrivers; recent_hotfixes = $hotfixes; enabled_optional_features = $features } | ConvertTo-Json -Depth 6 -Compress"
        ),
    },
    "security_risky_file_metadata": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$roots = @((Join-Path $env:USERPROFILE 'Downloads'),(Join-Path $env:USERPROFILE 'Desktop'),$env:TEMP,(Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs\\Startup'),(Join-Path $env:ProgramData 'Microsoft\\Windows\\Start Menu\\Programs\\StartUp')); "
            "$extensions = @('.exe','.dll','.msi','.msp','.ps1','.psm1','.bat','.cmd','.com','.scr','.vbs','.vbe','.js','.jse','.wsf','.wsh','.hta','.lnk','.iso','.img'); "
            "$files = @(); $errors = @(); foreach ($root in $roots | Sort-Object -Unique) { if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }; try { $candidates = Get-ChildItem -LiteralPath $root -File -Recurse -Force -ErrorAction SilentlyContinue | Where-Object { $extensions -contains $_.Extension.ToLowerInvariant() } | Sort-Object LastWriteTime -Descending | Select-Object -First 300; foreach ($file in $candidates) { $signature = if ($file.Extension -in @('.exe','.dll','.msi','.msp','.ps1','.psm1','.psd1','.ps1xml','.cdxml')) { Get-AuthenticodeSignature -FilePath $file.FullName -ErrorAction SilentlyContinue } else { $null }; $hash = if ($file.Length -le 268435456) { (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256 -ErrorAction SilentlyContinue).Hash } else { $null }; $zone = try { [bool](Get-Item -LiteralPath $file.FullName -Stream Zone.Identifier -ErrorAction Stop) } catch { $false }; $files += [pscustomobject]@{ root = $root; path = $file.FullName; extension = $file.Extension; size_bytes = $file.Length; created = $file.CreationTimeUtc; modified = $file.LastWriteTimeUtc; signature = if ($signature) { $signature.Status.ToString() } else { 'NotApplicable' }; signer = if ($signature -and $signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { $null }; sha256 = $hash; mark_of_the_web = $zone } } } catch { $errors += [pscustomobject]@{ root = $root; error = $_.Exception.Message } } }; "
            "[pscustomobject]@{ searched_roots = @($roots | Sort-Object -Unique); matched_file_count = $files.Count; files = $files; errors = $errors; per_root_limit = 300; hash_size_limit_bytes = 268435456 } | ConvertTo-Json -Depth 6 -Compress"
        ),
    },
    "security_wsl_posture": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "printf '%s\\n' '---identity---'\n"
            "id\n"
            "uname -a\n"
            "cat /etc/os-release\n"
            "printf '%s\\n' '---upgradable-packages-from-current-cache---'\n"
            "apt list --upgradable 2>/dev/null || true\n"
            "printf '%s\\n' '---failed-units---'\n"
            "systemctl --failed --no-pager 2>/dev/null || true\n"
            "printf '%s\\n' '---listening-sockets---'\n"
            "ss -lntup 2>/dev/null || ss -lntu\n"
            "printf '%s\\n' '---docker-containers---'\n"
            "docker ps --no-trunc --format '{{json .}}' 2>/dev/null || true\n"
            "printf '%s\\n' '---docker-security-settings---'\n"
            "for container in $(docker ps -q 2>/dev/null); do docker inspect --format '{{json .}}' \"$container\" | python3 -c 'import json,sys; x=json.load(sys.stdin); h=x.get(\"HostConfig\",{}); print(json.dumps({\"name\":x.get(\"Name\",\"\").lstrip(\"/\"),\"image\":x.get(\"Config\",{}).get(\"Image\"),\"privileged\":h.get(\"Privileged\"),\"readonly_rootfs\":h.get(\"ReadonlyRootfs\"),\"network_mode\":h.get(\"NetworkMode\"),\"pid_mode\":h.get(\"PidMode\"),\"cap_add\":h.get(\"CapAdd\"),\"security_opt\":h.get(\"SecurityOpt\"),\"ports\":h.get(\"PortBindings\"),\"mounts\":[{\"type\":m.get(\"Type\"),\"source\":m.get(\"Source\"),\"destination\":m.get(\"Destination\"),\"rw\":m.get(\"RW\")} for m in x.get(\"Mounts\",[])]}))' || true; done\n"
            "printf '%s\\n' '---setuid-setgid-files---'\n"
            "find /usr /bin /sbin -xdev -type f -perm /6000 -print 2>/dev/null | sort\n"
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
    "network_profile_status": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "Get-NetConnectionProfile | Select-Object InterfaceAlias,NetworkCategory,IPv4Connectivity,IPv6Connectivity | ConvertTo-Json -Compress"
        ),
    },
    "health_dashboard_windows_probe": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$listeners = @(Get-NetTCPConnection -State Listen -LocalPort 8080 -ErrorAction SilentlyContinue); "
            "$response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 http://127.0.0.1:8080/healthz; "
            "[pscustomobject]@{ listener_count = $listeners.Count; listener_addresses = @($listeners | ForEach-Object LocalAddress); local_health_status = $response.StatusCode } | ConvertTo-Json -Compress"
        ),
    },
    "health_dashboard_lan_proxy_enable": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$profiles = @(Get-NetConnectionProfile | Where-Object NetworkCategory -eq 'Private'); "
            "if ($profiles.Count -ne 1) { throw 'Refusing dashboard proxy: exactly one active Private network profile is required.' }; "
            "$addresses = @(Get-NetIPAddress -InterfaceIndex $profiles[0].InterfaceIndex -AddressFamily IPv4 | Where-Object { $_.IPAddress -notmatch '^169\\.254\\.' }); "
            "if ($addresses.Count -ne 1) { throw 'Refusing dashboard proxy: exactly one usable Private-network IPv4 address is required.' }; "
            "$listenAddress = $addresses[0].IPAddress; $existing = (& netsh.exe interface portproxy show v4tov4) -join \"`n\"; "
            "$line = ($existing -split \"`n\" | Where-Object { $_ -match ('^\\s*' + [regex]::Escape($listenAddress) + '\\s+8080\\s+') }); "
            "if ($line -and $line -notmatch '127\\.0\\.0\\.1\\s+8080\\s*$') { throw 'Refusing dashboard proxy: TCP 8080 already has a different port-proxy target.' }; "
            "if (-not $line) { & netsh.exe interface portproxy add v4tov4 listenaddress=$listenAddress listenport=8080 connectaddress=127.0.0.1 connectport=8080; if ($LASTEXITCODE -ne 0) { throw 'netsh portproxy add failed.' } }; "
            "$response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 ('http://' + $listenAddress + ':8080/healthz'); "
            "[pscustomobject]@{ listen_address = $listenAddress; listener_target = '127.0.0.1:8080'; local_health_status = $response.StatusCode; private_profile = $profiles[0].Name } | ConvertTo-Json -Compress"
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
    "m5_backup_status": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "manifest=\"$(find postgres/backup -maxdepth 1 -type f -name '*.manifest.json' -printf '%T@ %p\\n' | sort -nr | head -n 1 | cut -d' ' -f2-)\"\n"
            "[[ -n \"$manifest\" && -f \"$manifest\" ]] || { printf 'M5_BACKUP_UNAVAILABLE no manifest\\n' >&2; exit 4; }\n"
            "python3 scripts/backup_manifest.py verify \"$manifest\" >/dev/null\n"
            "printf 'M5_BACKUP_VERIFY_OK manifest=%s captured_at=%s scope=postgres-logical\\n' \"$(basename \"$manifest\")\" \"$(stat -c %y \"$manifest\")\"\n"
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
            "$bashCommand = 'for attempt in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 2; done; docker info >/dev/null; cd /home/chris/projects/cs-ai-lab-infra; docker compose up -d n8n; exec tail -f /dev/null'; "
            "$bashPayload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bashCommand)); "
            "$launcher = '$ErrorActionPreference = ''Stop''; $arguments = ''-d Ubuntu -- bash -c \"echo ' + $bashPayload + ' | base64 -d | bash\"''; $process = Start-Process -FilePath ''wsl.exe'' -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru; exit $process.ExitCode'; "
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
    "mt5_status": {
        "approval_required": False,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$terminal = 'C:\\Program Files\\GO Markets MT5\\terminal64.exe'; "
            "$task = Get-ScheduledTask -TaskName 'CS AI Lab MT5 Start' -ErrorAction SilentlyContinue; "
            "$info = if ($null -eq $task) { $null } else { Get-ScheduledTaskInfo -TaskName 'CS AI Lab MT5 Start' }; "
            "$processes = @(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Select-Object Id,StartTime,Path); "
            "[pscustomobject]@{ executable = $terminal; executable_present = Test-Path -LiteralPath $terminal -PathType Leaf; "
            "running = ($processes.Count -gt 0); processes = $processes; startup_task_present = ($null -ne $task); "
            "startup_task_state = if ($null -eq $task) { $null } else { $task.State.ToString() }; "
            "startup_task_last_result = if ($null -eq $info) { $null } else { $info.LastTaskResult }; "
            "startup_task_triggers = if ($null -eq $task) { @() } else { @($task.Triggers | ForEach-Object { $_.CimClass.CimClassName }) } } | ConvertTo-Json -Depth 4 -Compress"
        ),
    },
    "mt5_startup_enable": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$terminal = 'C:\\Program Files\\GO Markets MT5\\terminal64.exe'; "
            "if (-not (Test-Path -LiteralPath $terminal -PathType Leaf)) { throw 'Approved GO Markets MT5 terminal executable is absent.' }; "
            "$taskName = 'CS AI Lab MT5 Start'; $stateDir = Join-Path $env:ProgramData 'CSAILab'; New-Item -ItemType Directory -Force -Path $stateDir | Out-Null; "
            "$rollbackPath = Join-Path $stateDir 'CS-AI-Lab-MT5-Start.pre-change.xml'; "
            "$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue; if ($null -ne $existing) { Export-ScheduledTask -TaskName $taskName | Set-Content -Path $rollbackPath -Encoding utf8 }; "
            "$launcher = '$ErrorActionPreference = ''Stop''; $terminal = ''C:\\Program Files\\GO Markets MT5\\terminal64.exe''; if (-not (Test-Path -LiteralPath $terminal -PathType Leaf)) { throw ''Approved GO Markets MT5 terminal executable is absent.'' }; if (-not (Get-Process -Name terminal64 -ErrorAction SilentlyContinue)) { Start-Process -FilePath $terminal | Out-Null }; Start-Sleep -Seconds 15; if (-not (Get-Process -Name terminal64 -ErrorAction SilentlyContinue)) { throw ''MT5 did not remain running after launch.'' }'; "
            "$payload = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($launcher)); "
            "$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand ' + $payload); "
            "$trigger = New-ScheduledTaskTrigger -AtStartup; $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest; "
            "$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew; "
            "Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Starts only the approved GO Markets MT5 terminal at Windows boot; it performs no trading or account action.' -Force | Out-Null; "
            "$task = Get-ScheduledTask -TaskName $taskName; [pscustomobject]@{ task_name = $task.TaskName; principal = $task.Principal.UserId; logon_type = $task.Principal.LogonType.ToString(); triggers = @($task.Triggers | ForEach-Object { $_.CimClass.CimClassName }); rollback_saved = Test-Path $rollbackPath } | ConvertTo-Json -Compress"
        ),
    },
    "mt5_start": {
        "approval_required": True,
        "command": (
            "$ErrorActionPreference = 'Stop'; "
            "$task = Get-ScheduledTask -TaskName 'CS AI Lab MT5 Start' -ErrorAction SilentlyContinue; if ($null -eq $task) { throw 'MT5 startup task is absent; enable it first.' }; "
            "Start-ScheduledTask -TaskName 'CS AI Lab MT5 Start'; "
            "for ($attempt = 1; $attempt -le 20; $attempt++) { $processes = @(Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Select-Object Id,StartTime,Path); if ($processes.Count -gt 0) { [pscustomobject]@{ running = $true; processes = $processes } | ConvertTo-Json -Depth 3 -Compress; exit 0 }; Start-Sleep -Seconds 2 }; "
            "throw 'MT5 did not become running after the governed startup task.'"
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
            "$bashCommand = 'for attempt in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 2; done; docker info >/dev/null; cd /home/chris/projects/cs-ai-lab-infra; docker compose up -d n8n; exec tail -f /dev/null'\n"
            "$payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bashCommand))\n"
            "$arguments = '-d Ubuntu -- bash -c \"echo ' + $payload + ' | base64 -d | bash\"'\n"
            "$process = Start-Process -FilePath 'wsl.exe' -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath\n"
            "exit $process.ExitCode\n"
            "'@; Set-Content -Path $scriptPath -Value $script -Encoding utf8; "
            "$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"' + $scriptPath + '\"'); "
            "$trigger = New-ScheduledTaskTrigger -AtLogOn; "
            "$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -MultipleInstances IgnoreNew; "
            "Register-ScheduledTask -TaskName 'CS AI Lab Start' -Action $action -Trigger $trigger "
            "-Settings $settings -Description 'Starts T480 Ubuntu WSL, waits for Docker, starts private PostgreSQL and n8n, and keeps WSL alive at sign-in.' -Force | Out-Null; "
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
    "ollama_qwen25_3b_install": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "docker compose --profile ollama up -d --wait --wait-timeout 180 ollama\n"
            "docker compose exec -T ollama ollama pull qwen2.5:3b\n"
            "docker compose exec -T ollama ollama list | grep -E '^qwen2.5:3b[[:space:]]'\n"
            "echo ollama-qwen25-3b-install-complete\n"
        ),
    },
    "ollama_qwen25_3b_status": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "docker compose exec -T ollama ollama list\n"
            "state_dir=/home/chris/.local/state/cs-ai-lab\n"
            "pid_file=\"$state_dir/ollama-qwen25-3b-install.pid\"\n"
            "log_file=\"$state_dir/ollama-qwen25-3b-install.log\"\n"
            "echo ---installation-job---\n"
            "if [ -f \"$pid_file\" ] && kill -0 \"$(cat \"$pid_file\")\" 2>/dev/null; then echo running; else echo not-running; fi\n"
            "echo ---installation-log---\n"
            "test -f \"$log_file\" && tail -n 40 \"$log_file\" || echo absent\n"
        ),
    },
    "ollama_qwen25_3b_recover": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "docker compose --profile ollama restart ollama\n"
            "docker compose --profile ollama up -d --wait --wait-timeout 90 ollama\n"
            "docker compose exec -T ollama ollama list | grep -E '^qwen2.5:3b[[:space:]]'\n"
            "echo ollama-qwen25-3b-recovery-complete\n"
        ),
    },
    "ollama_qwen25_3b_diagnostics": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "state_dir=/home/chris/.local/state/cs-ai-lab\n"
            "pid_file=\"$state_dir/ollama-qwen25-3b-install.pid\"\n"
            "log_file=\"$state_dir/ollama-qwen25-3b-install.log\"\n"
            "echo ---pid---\n"
            "test -f \"$pid_file\" && cat \"$pid_file\" || echo absent\n"
            "echo ---running---\n"
            "if [ -f \"$pid_file\" ] && kill -0 \"$(cat \"$pid_file\")\" 2>/dev/null; then echo true; else echo false; fi\n"
            "echo ---log---\n"
            "test -f \"$log_file\" && tail -n 120 \"$log_file\" || echo absent\n"
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
    "openworker_deploy": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "root=/home/chris/projects/cs-ai-lab-infra\n"
            "git -C \"$root\" diff --quiet && git -C \"$root\" diff --cached --quiet || { echo 'Refusing: T480 lab checkout has local changes.' >&2; exit 4; }\n"
            "git -C \"$root\" fetch --depth 1 origin main\n"
            "git -C \"$root\" checkout --detach FETCH_HEAD\n"
            "exec \"$root/scripts/openworker-deploy.sh\"\n"
        ),
    },
    "openworker_status": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/openworker\n"
            "./scripts/openworker-status.sh\n"
        ),
    },
    "openworker_diagnostics": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/openworker\n"
            "echo ---revision---\n"
            "git rev-parse HEAD\n"
            "echo ---compose-validation---\n"
            "docker compose config --quiet\n"
            "echo valid\n"
            "echo ---images---\n"
            "docker compose images || true\n"
            "echo ---containers---\n"
            "docker compose ps -a\n"
            "echo ---api-log---\n"
            "docker compose logs --tail 100 api || true\n"
            "echo ---ui-log---\n"
            "docker compose logs --tail 100 ui || true\n"
            "echo ---deployment-log---\n"
            "tail -n 100 /home/chris/.local/state/cs-ai-lab/openworker-deploy.log 2>/dev/null || true\n"
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
            "expected_image='n8nio/n8n:1.123.76@sha256:66b6bfd6716877591d9c21340250f44f842e6b03f97ccaed09b9f95e13cf5331'\n"
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
    "repository_snapshot_and_update": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "repository_root='/home/chris/projects/cs-ai-lab-infra'\n"
            "repository_url='https://github.com/successbycs/cs-ai-lab-infra.git'\n"
            "cd \"$repository_root\"\n"
            "[[ \"$(git remote get-url origin)\" == \"$repository_url\" ]] || { printf 'Refusing recovery: origin differs.\\n' >&2; exit 4; }\n"
            "test -n \"$(git status --porcelain --untracked-files=normal)\" || { printf 'Refusing recovery: checkout is already clean; use repository_update.\\n' >&2; exit 4; }\n"
            "timestamp=\"$(date -u +%Y%m%dT%H%M%SZ)\"\n"
            "backup_root=\"/home/chris/.local/state/cs-ai-lab/repository-recovery-$timestamp\"\n"
            "mkdir -p \"$backup_root\"\n"
            "git status --porcelain=v1 --untracked-files=all > \"$backup_root/status.txt\"\n"
            "git rev-parse HEAD > \"$backup_root/original-head.txt\"\n"
            "git diff --binary HEAD > \"$backup_root/tracked-worktree.patch\"\n"
            "git diff --cached --binary > \"$backup_root/staged.patch\"\n"
            "git apply --check --reverse \"$backup_root/tracked-worktree.patch\"\n"
            "sha256sum \"$backup_root\"/*.txt \"$backup_root\"/*.patch > \"$backup_root/SHA256SUMS\"\n"
            "git fetch origin main\n"
            "git reset --hard origin/main\n"
            "test -z \"$(git status --porcelain --untracked-files=normal)\" || { printf 'Recovery reset did not produce a clean tracked checkout.\\n' >&2; exit 5; }\n"
            "printf 'REPOSITORY_RECOVERY_OK backup=%s revision=%s\\n' \"$backup_root\" \"$(git rev-parse HEAD)\"\n"
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
    "penpot_preflight": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "./penpot/scripts/preflight.sh\n"
            "if [[ -f /home/chris/.config/cs-ai-lab/penpot.env ]]; then ./penpot/scripts/bootstrap.sh; fi\n"
        ),
    },
    "penpot_deploy": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "./penpot/scripts/preflight.sh\n"
            "./penpot/scripts/bootstrap.sh\n"
            "./penpot/scripts/start.sh\n"
        ),
    },
    "penpot_start": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "./penpot/scripts/start.sh\n"
        ),
    },
    "penpot_health": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "./penpot/scripts/health.sh\n"
        ),
    },
    "penpot_diagnostics": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "source ./penpot/scripts/lib.sh\n"
            "require_env_file\n"
            "compose ps\n"
            "compose logs --tail 80 penpot-frontend penpot-backend penpot-exporter penpot-mcp\n"
        ),
    },
    "penpot_disable": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "./penpot/scripts/stop.sh\n"
        ),
    },
    "penpot_verification_profile": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "./penpot/scripts/create-verification-profile.sh\n"
        ),
    },
    "penpot_backup": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "./penpot/scripts/backup.sh\n"
        ),
    },
    "penpot_restore_test": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "./penpot/scripts/restore-test.sh\n"
        ),
    },
    "penpot_persistence_test": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "./penpot/scripts/restart-persistence-test.sh\n"
        ),
    },
    "penpot_rollback_test": {
        "approval_required": True,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "./penpot/scripts/rollback-test.sh\n"
        ),
    },
    "penpot_resource_report": {
        "approval_required": False,
        "wsl_script": (
            "set -euo pipefail\n"
            "cd /home/chris/projects/cs-ai-lab-infra\n"
            "./penpot/scripts/resource-report.sh\n"
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
    encoded_payload = base64.b64encode(gzip.compress(json.dumps(summary, separators=(",", ":")).encode())).decode("ascii")
    if not re.fullmatch(r"[A-Za-z0-9+/=]+", encoded_payload):
        raise RuntimeError("Healthcheck summary could not be encoded safely.")
    script = f"""set -euo pipefail
cd /home/chris/projects/cs-ai-lab-infra
set -a
source .env
set +a
payload_b64='{encoded_payload}'
payload_json=\"$(printf '%s' \"$payload_b64\" | base64 -d | gzip -d)\"
record_sql=\"SELECT monitoring.record_healthcheck(:'payload_json'::jsonb);\"
printf '%s\\n' \"$record_sql\" | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -v payload_json=\"$payload_json\" -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\"
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
