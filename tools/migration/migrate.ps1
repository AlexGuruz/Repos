<#
.SYNOPSIS
  Create zone dirs and move folders per layout.json (logged transaction).
  Continues on lock errors; uses robocopy /MOVE fallback when Move-Item fails.
.EXAMPLE
  .\migrate.ps1 -DryRun
  .\migrate.ps1 -Apply
#>
param(
    [switch]$DryRun,
    [switch]$Apply,
    [switch]$SkipPreflight
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib\Layout.ps1"

if (-not $DryRun -and -not $Apply) { $DryRun = $true }

$root = Get-ReposRoot
$layout = Get-MigrationLayout
$stamp = New-ReportStamp
$reports = Get-ReportsDir
$logPath = Join-Path $reports "migrate-$stamp.log"
$jsonLog = Join-Path $reports "migrate-$stamp.json"

if (-not $SkipPreflight -and $Apply) {
    & "$PSScriptRoot\clear_locks.ps1" -Apply
    & "$PSScriptRoot\preflight.ps1"
    if ($LASTEXITCODE -ne 0) { throw "Preflight failed" }
}

function Move-Children {
    param([string]$From, [string]$To, [string[]]$SkipNames = @('.claude'))
    New-Item -ItemType Directory -Force -Path $To | Out-Null
    $partial = $false
    foreach ($child in (Get-ChildItem -LiteralPath $From -Force -ErrorAction SilentlyContinue)) {
        if ($SkipNames -contains $child.Name) {
            Write-MigLog "SKIP lock-magnet: $($child.Name)" 'WARN'
            $partial = $true
            continue
        }
        $target = Join-Path $To $child.Name
        if (Test-Path -LiteralPath $target) {
            if ($child.PSIsContainer) {
                $left = @(Get-ChildItem -LiteralPath $child.FullName -Force -ErrorAction SilentlyContinue)
                if ($left.Count -gt 0) {
                    Write-MigLog "MERGE child $($child.Name)"
                    $null = Move-Children -From $child.FullName -To $target -SkipNames $SkipNames
                    $still = @(Get-ChildItem -LiteralPath $child.FullName -Force -ErrorAction SilentlyContinue)
                    if ($still.Count -eq 0) {
                        Remove-Item -LiteralPath $child.FullName -Force -Recurse -ErrorAction SilentlyContinue
                    } else { $partial = $true }
                }
            }
            continue
        }
        try {
            Move-Item -LiteralPath $child.FullName -Destination $target -ErrorAction Stop
        } catch {
            Write-MigLog "child move fail $($child.Name): $_" 'WARN'
            $partial = $true
        }
    }
    return (-not $partial)
}

function Move-Logged {
    param([string]$From, [string]$To, [string]$Kind)
    $entry = [pscustomobject]@{ kind = $Kind; from = $From; to = $To; status = 'pending'; note = '' }
    if (-not (Test-Path -LiteralPath $From)) {
        Write-MigLog "SKIP missing: $From" 'WARN'
        $entry.status = 'skip-missing'
        return $entry
    }
    if (Test-Path -LiteralPath $To) {
        $srcLeft = @(Get-ChildItem -LiteralPath $From -Force -ErrorAction SilentlyContinue)
        if ($Apply -and $srcLeft.Count -gt 0) {
            Write-MigLog "MERGE leftovers via children $From -> $To" 'WARN'
            $ok = Move-Children -From $From -To $To
            $still = @(Get-ChildItem -LiteralPath $From -Force -ErrorAction SilentlyContinue)
            if ($ok -and $still.Count -eq 0) {
                Remove-Item -LiteralPath $From -Force -Recurse -ErrorAction SilentlyContinue
                $entry.status = 'merged'
            } elseif ($still.Count -eq 0) {
                Remove-Item -LiteralPath $From -Force -Recurse -ErrorAction SilentlyContinue
                $entry.status = 'merged'
            } else {
                $entry.status = 'partial-locked'
                $entry.note = "leftovers: $($still.Name -join ', ')"
                Write-MigLog "PARTIAL leftovers in $From : $($still.Name -join ', ')" 'WARN'
            }
            return $entry
        }
        Write-MigLog "SKIP exists: $To" 'WARN'
        $entry.status = 'skip-exists'
        return $entry
    }
    $parent = Split-Path -Parent $To
    Write-MigLog "$(if ($Apply) {'MOVE'} else {'DRY'}) $From -> $To"
    "MOVE $From -> $To" | Add-Content -LiteralPath $logPath -Encoding UTF8
    if ($Apply) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
        try {
            Move-Item -LiteralPath $From -Destination $To -ErrorAction Stop
            $entry.status = 'moved'
        } catch {
            Write-MigLog "Move-Item failed, moving children instead: $_" 'WARN'
            $ok = Move-Children -From $From -To $To
            $still = @(Get-ChildItem -LiteralPath $From -Force -ErrorAction SilentlyContinue)
            if ($still.Count -eq 0) {
                Remove-Item -LiteralPath $From -Force -Recurse -ErrorAction SilentlyContinue
                $entry.status = 'moved-children'
            } else {
                $entry.status = 'partial-locked'
                $entry.note = "leftovers: $($still.Name -join ', ')"
                Write-MigLog "PARTIAL: $From leftovers $($still.Name -join ', ')" 'WARN'
            }
        }
    } else {
        $entry.status = 'dry-run'
    }
    return $entry
}

Write-MigLog "migrate $(if ($Apply) {'APPLY'} else {'DRY-RUN'}) root=$root"
"" | Set-Content -LiteralPath $logPath -Encoding UTF8
$results = @()

foreach ($z in $layout.zones) {
    $zp = Join-Path $root $z
    if ($Apply) {
        New-Item -ItemType Directory -Force -Path $zp | Out-Null
    }
    Write-MigLog "Zone: $zp"
}

foreach ($m in $layout.moves) {
    $from = Join-Path $root $m.from
    $to = Join-Path $root ($m.to -replace '/', '\')
    $results += Move-Logged -From $from -To $to -Kind 'dir'
}

foreach ($m in $layout.file_moves) {
    $from = Join-Path $root $m.from
    $to = Join-Path $root ($m.to -replace '/', '\')
    $results += Move-Logged -From $from -To $to -Kind 'file'
}

$results | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $jsonLog -Encoding UTF8
Write-MigLog "Log: $logPath"
Write-MigLog "JSON: $jsonLog"
$moved = @($results | Where-Object status -in @('moved','moved-children','merged')).Count
$partial = @($results | Where-Object status -eq 'partial-locked').Count
$err = @($results | Where-Object status -eq 'error').Count
Write-MigLog "Done moved=$moved partial=$partial errors=$err"
if ($partial -gt 0 -or $err -gt 0) { exit 2 }
exit 0
