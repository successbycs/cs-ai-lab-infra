[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [ValidatePattern('^http://localhost:9001/#/workspace\?')]
  [string]$FileUrl,
  [Parameter(Mandatory = $true)]
  [string]$ProfileRoot,
  [string]$ChromePath = "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"
)

$ErrorActionPreference = 'Stop'

# This launcher deliberately accepts an existing, dedicated profile only. It
# never creates a profile, logs in, reads cookies, or handles a Penpot token.
# Run it from the service account's interactive Windows session, not as a
# scheduled task or a Windows service (those run in session 0 and cannot host
# the Penpot browser plugin).
if (-not (Test-Path -LiteralPath $ChromePath -PathType Leaf)) {
  throw "Chrome was not found at the supplied ChromePath."
}
if (-not (Test-Path -LiteralPath $ProfileRoot -PathType Container)) {
  throw "The dedicated existing Chrome profile directory is required; refusing to create one."
}
if (-not (Test-Path -LiteralPath (Join-Path $ProfileRoot 'Local State') -PathType Leaf)) {
  throw "ProfileRoot does not look like an existing Chrome user-data directory."
}
if (-not (Get-Process explorer -ErrorAction SilentlyContinue)) {
  throw "No interactive Windows desktop session was found. Run this as the dedicated service account."
}

Start-Process -FilePath $ChromePath -ArgumentList @(
  "--user-data-dir=$ProfileRoot",
  '--new-window',
  $FileUrl
)

Write-Output 'Managed service-account browser started.'
Write-Output 'In that browser, confirm the dedicated Penpot account and use File > MCP Server > Connect for this file.'
Write-Output 'Keep the tab open while MCP work is active; its profile retains no secrets in this script.'
