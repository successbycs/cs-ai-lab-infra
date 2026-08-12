# T480 provisioning log

This is the running record for preparing the T480 as the private AI Lab server. It records safe operational evidence, commands, and next steps. Do not add passwords, private keys, API keys, or the home-network IP address to this file.

Last updated: 2026-08-12

## Completed: AC-powered availability policy

- [x] Confirmed the active Windows Balanced plan already disables AC sleep.
- [x] Changed AC timed hibernation from three hours to never.
- [x] Set the AC lid-close action to do nothing.
- [x] Preserved the existing battery (DC) sleep and hibernation policy.

The fixed T480 adapter operation `power_policy_ac_always_on` applies this policy with explicit approval; `power_policy_status` reads it back. This avoids ordinary AC idle or lid-close events interrupting WSL/Docker. It does not replace M5's required boot-triggered Local System task for no-logon recovery after a Windows restart.

## Completed: network discovery

- [x] Confirmed the T480 hostname: `T480-Desktop`.
- [x] Identified the T480's Wi-Fi IPv4 address locally.
- [x] Confirmed both laptops are on the same local network.

Commands used:

```powershell
# Run on the T480 in PowerShell.
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike '169.254*' -and $_.InterfaceAlias -notmatch 'Loopback' } |
  Select-Object IPAddress, InterfaceAlias

# Run on the T16 in PowerShell, substituting the T480's IPv4 address.
Test-NetConnection <T480_IP> -Port 22
```

Success evidence:

```text
TcpTestSucceeded : True
```

This confirms the T16 can establish a TCP connection to the T480's SSH port. Windows firewall blocking ping replies is not relevant now that the TCP test has succeeded.

## Completed: SSH server installation

- [x] Confirmed the Windows OpenSSH Client was already installed.
- [x] Confirmed the Windows OpenSSH Server was initially absent.
- [x] Installed the built-in Windows OpenSSH Server.
- [x] Started the `sshd` service.
- [x] Verified that port 22 is reachable from the T16.

Commands used on the T480 in an Administrator PowerShell window:

```powershell
Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH*'
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Get-Service sshd
```

The intended persistence command is:

```powershell
Set-Service -Name sshd -StartupType Automatic
```

Status: SSH is confirmed running now. Confirm the automatic-start setting after running the command above with:

```powershell
Get-CimInstance Win32_Service -Filter "Name='sshd'" |
  Select-Object Name, State, StartMode
```

## Next: first remote login

From the T16, connect with the Windows account used on the T480:

```powershell
ssh <T480_WINDOWS_USERNAME>@<T480_IP>
```

On the first connection, verify the displayed host fingerprint is accepted deliberately, then enter the T480 account password when prompted. Do not record the password in this file.

Success looks like a remote prompt similar to:

```text
<T480_WINDOWS_USERNAME>@T480-Desktop C:\Users\<T480_WINDOWS_USERNAME>>
```

## Completed: first remote login

- [x] Connected from the T16 to the T480 using SSH.
- [x] Accepted and saved the T480's first-use SSH host key on the T16.
- [x] Used password authentication for the initial connection.
- [x] Confirmed the remote hostname is `T480-Desktop`.

The SSH session opens in Windows Command Prompt (`cmd.exe`), not PowerShell. Use Command Prompt-compatible inspection commands below, or explicitly start PowerShell with `powershell` when a PowerShell cmdlet is needed.

Security note: the T480 Windows password is **not** stored in `.env` or this repository. The next security improvement, after the runtime is selected, is SSH key-based login from the T16.

## Next: inspect the Linux runtime options

The infrastructure repository is designed for the T480's Linux runtime. After confirming remote access, the next decision is whether to use WSL2/Linux on this Windows T480 or install a dedicated Linux OS. We will inspect the current setup before changing it, then install Docker and deploy the lab only after the chosen runtime is ready.

Confirmed platform:

- [x] Windows 11 Pro, build 22621.
- [x] x64-based PC.
- [x] Checked WSL command availability.
- [x] Confirmed no usable Linux distribution is currently configured.
- [x] Confirmed that Ubuntu is available through `wsl --install`.
- [ ] Choose the runtime path before making changes: WSL2 + Ubuntu, or native Linux.

Evidence: `wsl --list --verbose` returned the WSL installation help rather than a distribution list. No Linux distribution is ready to host Docker yet.

Available distributions were checked with:

```bat
wsl --list --online
```

Ubuntu is the default available distribution.

### Runtime decision

**Fastest route — WSL2 + Ubuntu:** retains Windows, installs Ubuntu alongside it, and is appropriate for early learning. It introduces Windows/WSL/Docker integration overhead and makes a permanently unattended server less clean.

**Recommended long-term route — native Ubuntu Server:** replaces Windows with Linux and best matches this repository's Docker/Linux assumptions. It is simpler to operate as a dedicated lab server, but requires backing up any T480 data first and reinstalling the operating system.

## In progress: WSL2 + Ubuntu installation

- [x] Started installation with `wsl --install -d Ubuntu`.
- [x] Installed the Windows Virtual Machine Platform feature.
- [x] Installed the Windows Subsystem for Linux feature.
- [x] Downloaded and installed the Ubuntu distribution.
- [x] Confirmed that Windows requires a restart before the changes take effect.
- [x] Rebooted the T480.
- [x] Completed Ubuntu's first-run user setup.
- [x] Confirmed that an Ubuntu shell is available on the T480.
- [x] Confirmed Ubuntu 26.04 LTS is installed.
- [x] Confirmed WSL can access 8 logical CPU threads.
- [x] Confirmed `systemd` is enabled in Ubuntu.
- [x] Created and verified `C:\Users\OEM\.wslconfig` with a 20 GB memory cap, 6 CPU threads, 4 GB swap, and localhost forwarding.
- [x] Restarted WSL and confirmed 6 CPU threads, 4 GB swap, and `systemd` are active.
- [x] Verified 15.8 GB physical RAM; the initial 32 GB hardware assumption was incorrect.
- [x] Reduced the WSL memory cap to 10 GB and restarted WSL.
- [x] Confirmed the final WSL runtime: 9.7 GiB RAM, 6 CPU threads, 4 GB swap, and `systemd`.
- [ ] Inspect CPU architecture, disk, memory, and WSL runtime before installing Docker.

Command used in the T480 SSH session:

```bat
wsl --install -d Ubuntu
```

Installation completed successfully and Windows reported that a restart is required before the changes take effect.

After reboot, Ubuntu required a first launch with:

```bat
wsl -d Ubuntu
```

The initial Ubuntu user was created interactively. Do not record the Linux password in this repository.

## Next: inspect Ubuntu readiness

Run these read-only commands inside the Ubuntu shell, one at a time:

```bash
whoami
cat /etc/os-release
uname -m
free -h
df -h /
```

These confirm the Linux account, Ubuntu release, CPU architecture, available memory, and available disk before Docker is installed.

### Current capacity constraint

- [x] Reported approximately 30 GB free on the T480's base Windows drive.
- [x] Removed Visual Studio Community 2022.
- [x] Rechecked storage after removal: 68.8 GB free on C: (34.7 GB recovered).
- [x] Removed 8 GB of unneeded videos and rechecked storage: 80.2 GB free on C:.
- [x] Reached the minimum free-space target for the initial Docker stack.
- [ ] Reclaim additional storage before downloading local models; 100 GB free remains the preferred target.

Thirty GB is enough to explore Ubuntu itself, but is not enough headroom for durable Docker images, PostgreSQL data, backups, and model files. The Visual Studio removal and video cleanup raised free space to 80.2 GB, which is enough for the initial Docker stack. Reach 100 GB free before downloading local models or accumulating substantial backups.

### Storage audit findings

- [x] Scanned high-level Windows storage categories.
- [x] Scanned the Windows user profile.
- [x] Identified `AppData` as the main user-profile storage area (47.3 GB reported).
- [x] Identified `Videos` (9.8 GB), `Downloads` (2.6 GB), `.gradle` (1.3 GB), and `.rustup` (0.6 GB) as additional candidates for review.
- [ ] Inspect the real `AppData\Local` subfolders before removing application data.

Important: `Local Settings` and `Application Data` are Windows compatibility junctions into `AppData`; their reported sizes overlap with `AppData` and must not be added together or deleted as separate folders.

Run these read-only commands in the SSH session (`cmd.exe`):

```bat
hostname
systeminfo | findstr /B /C:"OS Name" /C:"OS Version" /C:"System Type"
wsl --status
wsl --list --verbose
```

Record the resulting Windows version, virtualisation/WSL availability, and any installed Linux distributions before selecting the runtime.
