# T480 provisioning log

This is the running record for preparing the T480 as the private AI Lab server. It records safe operational evidence, commands, and next steps. Do not add passwords, private keys, API keys, or the home-network IP address to this file.

Last updated: 2026-08-11

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
- [ ] Ubuntu distribution download and installation in progress.
- [ ] Restart requirement to be confirmed after installation completes.

Command used in the T480 SSH session:

```bat
wsl --install -d Ubuntu
```

Do not interrupt the installation while Ubuntu is downloading. Once it completes, capture the final message before restarting or continuing.

Run these read-only commands in the SSH session (`cmd.exe`):

```bat
hostname
systeminfo | findstr /B /C:"OS Name" /C:"OS Version" /C:"System Type"
wsl --status
wsl --list --verbose
```

Record the resulting Windows version, virtualisation/WSL availability, and any installed Linux distributions before selecting the runtime.
