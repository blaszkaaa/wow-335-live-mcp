param(
    [Parameter(Mandatory = $true)]
    [string]$GameDir
)

$ErrorActionPreference = 'Stop'

$game = (Resolve-Path -LiteralPath $GameDir).Path
if (-not (Test-Path -LiteralPath (Join-Path $game 'Wow.exe') -PathType Leaf)) {
    throw 'GameDir must contain Wow.exe.'
}

$source = Join-Path (Split-Path -Parent $PSScriptRoot) 'WoWMCPData'
$addons = Join-Path $game 'Interface\AddOns'
$destination = Join-Path $addons 'WoWMCPData'
New-Item -ItemType Directory -Force -Path $addons | Out-Null

if (Test-Path -LiteralPath $destination) {
    $backupRoot = Join-Path $game 'Interface\AddOns-backups'
    New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $backup = Join-Path $backupRoot "WoWMCPData-$stamp"
    Copy-Item -LiteralPath $destination -Destination $backup -Recurse
    Write-Host "Existing addon backed up to: $backup"
} else {
    New-Item -ItemType Directory -Path $destination | Out-Null
}

foreach ($name in @('WoWMCPData.toc', 'WoWMCPData.lua')) {
    Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $destination $name) -Force
}

Write-Host "Installed WoWMCPData in: $destination"
Write-Host 'Enable it on the character selection AddOns screen, then enter the world or use /reload.'
