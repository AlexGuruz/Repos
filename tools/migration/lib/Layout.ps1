# Shared bootstrap for tools/migration/*.ps1
# Dot-source: . "$PSScriptRoot\lib\Layout.ps1"  from a script in tools/migration/
$ErrorActionPreference = 'Stop'

# This file lives in tools/migration/lib/
$script:MigrationRoot = Split-Path -Parent $PSScriptRoot
Import-Module (Join-Path $script:MigrationRoot 'lib\Paths.psm1') -Force

function Get-ReportsDir {
    $d = Join-Path $script:MigrationRoot 'reports'
    New-Item -ItemType Directory -Force -Path $d | Out-Null
    return $d
}

function New-ReportStamp {
    return (Get-Date -Format 'yyyyMMdd-HHmmss')
}

function Write-MigLog {
    param([string]$Message, [string]$Level = 'INFO')
    $line = "[{0}] [{1}] {2}" -f (Get-Date -Format 'o'), $Level, $Message
    Write-Host $line
}

function Get-MigrationLayout {
    return Get-LayoutObject
}
