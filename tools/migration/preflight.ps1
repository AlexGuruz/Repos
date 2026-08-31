<#
.SYNOPSIS
  Preflight gate before migrate. Exit 0 = OK, 1 = fail.
#>
param(
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib\Layout.ps1"

$root = Get-ReposRoot
$layout = Get-MigrationLayout
$ok = $true

Write-MigLog "Preflight REPOS_ROOT=$root status=$(Get-LayoutStatus)"

# layout.json valid
try {
    $null = $layout.moves
    Write-MigLog "layout.json OK ($($layout.moves.Count) moves)"
} catch {
    Write-MigLog "layout.json invalid: $_" 'ERROR'
    $ok = $false
}

# Free space on E:
try {
    $drive = Get-PSDrive -Name E -ErrorAction SilentlyContinue
    if ($drive) {
        $freeGB = [math]::Round($drive.Free / 1GB, 2)
        Write-MigLog "E: free space ${freeGB} GB"
        if ($freeGB -lt 5) {
            Write-MigLog "Low disk on E: (<5GB)" 'WARN'
            if (-not $Force) { $ok = $false }
        }
    }
} catch { }

# Zone collision check
foreach ($z in $layout.zones) {
    $zp = Join-Path $root $z
    if (Test-Path -LiteralPath $zp) {
        Write-MigLog "Zone already exists: $z (OK if re-run)"
    }
}

# Critical sources exist
$missing = @()
foreach ($m in $layout.moves) {
    $src = Join-Path $root $m.from
    $dst = Join-Path $root ($m.to -replace '/', '\')
    if (-not (Test-Path -LiteralPath $src) -and -not (Test-Path -LiteralPath $dst)) {
        $missing += $m.from
    }
}
if ($missing.Count -gt 0) {
    Write-MigLog "Missing sources (will skip): $($missing -join ', ')" 'WARN'
}

# Git status hint
Push-Location $root
try {
    $gs = git status --porcelain 2>$null
    if ($gs) {
        Write-MigLog "Working tree has uncommitted changes ($($gs.Count) lines) - commit or stash recommended" 'WARN'
    } else {
        Write-MigLog "Git working tree clean (or not a git repo)"
    }
} finally { Pop-Location }

if (-not $ok) {
    Write-MigLog "PREFLIGHT FAILED" 'ERROR'
    exit 1
}
Write-MigLog "PREFLIGHT OK"
exit 0
