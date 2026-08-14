<#
.SYNOPSIS
  E:\ drive hygiene moves from layout.json edrive section.
#>
param(
    [switch]$DryRun,
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib\Layout.ps1"

if (-not $DryRun -and -not $Apply) { $DryRun = $true }

$layout = Get-MigrationLayout
$edrive = $layout.edrive
$personal = $edrive.personal
$archive = $edrive.archive

Write-MigLog "E-drive hygiene $(if ($Apply) {'APPLY'} else {'DRY-RUN'})"

if ($Apply) {
    New-Item -ItemType Directory -Force -Path $personal | Out-Null
    foreach ($sub in @('learning', 'vendors', 'duplicates', 'tmp')) {
        New-Item -ItemType Directory -Force -Path (Join-Path $archive $sub) | Out-Null
    }
}

# Loose JPG
$jpg = Get-ChildItem -LiteralPath 'E:\' -File -Filter '1000_F_*.jpg' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($jpg) {
    $dest = Join-Path $personal $jpg.Name
    Write-MigLog "$(if ($Apply) {'MOVE'} else {'DRY'}) $($jpg.FullName) -> $dest"
    if ($Apply -and -not (Test-Path $dest)) {
        Move-Item -LiteralPath $jpg.FullName -Destination $dest
    }
}

foreach ($m in $edrive.moves) {
    $from = $m.from
    $to = $m.to
    if (-not (Test-Path -LiteralPath $from)) {
        Write-MigLog "SKIP missing: $from" 'WARN'
        continue
    }
    if (Test-Path -LiteralPath $to) {
        Write-MigLog "SKIP exists: $to" 'WARN'
        continue
    }
    Write-MigLog "$(if ($Apply) {'MOVE'} else {'DRY'}) $from -> $to"
    if ($Apply) {
        $parent = Split-Path -Parent $to
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
        Move-Item -LiteralPath $from -Destination $to
    }
}

# README.txt
$readme = @'
E: drive layout
===============
Personal\   photos, dashcam, media
Repos\      business monorepo (products / internal / archive / vendor / tools)
secrets\    credentials — NEVER commit to git
_archive_E\ dated quarantine of experiments and vendor clones
Git\        tooling

See E:\Repos\docs\E_DRIVE_LAYOUT.md and E:\Repos\tools\migration\README.md
'@
$readmePath = 'E:\README.txt'
Write-MigLog "$(if ($Apply) {'WRITE'} else {'DRY'}) $readmePath"
if ($Apply) {
    Set-Content -LiteralPath $readmePath -Value $readme -Encoding UTF8
}

Write-MigLog "E-drive hygiene done"
