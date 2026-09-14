[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$ProfileRoot
)

$ErrorActionPreference = 'Stop'
$profileExists = Test-Path -LiteralPath (Join-Path $ProfileRoot 'Local State') -PathType Leaf
$interactiveDesktop = [bool](Get-Process explorer -ErrorAction SilentlyContinue)
$chromeRunning = [bool](Get-Process chrome -ErrorAction SilentlyContinue)

[pscustomobject]@{
  profileReady = $profileExists
  interactiveDesktop = $interactiveDesktop
  chromeRunning = $chromeRunning
  note = 'This checks local prerequisites only. Confirm MCP attachment in the open Penpot file.'
} | ConvertTo-Json -Compress
