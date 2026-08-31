<#
.SYNOPSIS
  Post-cut verification checklist.
#>
param()
$ErrorActionPreference = 'Continue'
. "$PSScriptRoot\lib\Layout.ps1"

$root = Get-ReposRoot
$layout = Get-MigrationLayout
$stamp = New-ReportStamp
$fail = 0
$lines = @("# Verify $stamp", "", "- Root: ``$root``", "- Status: ``$(Get-LayoutStatus)``", "")

function Check($name, [bool]$cond) {
    if ($cond) {
        $script:lines += "- PASS: $name"
        Write-Host "[PASS] $name" -ForegroundColor Green
    } else {
        $script:lines += "- FAIL: $name"
        Write-Host "[FAIL] $name" -ForegroundColor Red
        $script:fail++
    }
}

$status = Get-LayoutStatus
Check "layout status is migrated" ($status -eq 'migrated')

foreach ($z in $layout.zones) {
    Check "zone $z exists" (Test-Path (Join-Path $root $z))
}

foreach ($m in $layout.moves) {
    if ($m.status -notin @('production', 'internal', 'concept', 'archive', 'legacy', 'vendor', 'tooling', 'assets', 'templates', 'tmp')) { continue }
    $dst = Join-Path $root ($m.to -replace '/', '\')
    $src = Join-Path $root $m.from
    if (Test-Path $dst) {
        Check "present $($m.to)" $true
        Check "legacy gone $($m.from)" (-not (Test-Path $src))
    } elseif (Test-Path $src) {
        # Still legacy — not a fail if we haven't migrated yet
        $lines += "- SKIP: $($m.from) not moved yet"
    } else {
        Check "present $($m.to) or legacy $($m.from)" $false
    }
}

# Path helper smoke via python
$py = Join-Path $PSScriptRoot 'python\repos_paths.py'
if (Test-Path $py) {
    $pythonDir = Join-Path $PSScriptRoot 'python'
    $code = "import sys; sys.path.insert(0, r'$pythonDir'); import repos_paths as rp; print(rp.layout_status()); print(rp.product('ai-lab')); print(rp.product('growflow'))"
    try {
        $out = python -c $code 2>&1
        Check "python repos_paths import" ($LASTEXITCODE -eq 0)
        $lines += "- python: $($out -join ' | ')"
    } catch {
        Check "python repos_paths import" $false
    }
}

$outMd = Join-Path (Get-ReportsDir) "verify-$stamp.md"
$lines -join "`n" | Set-Content -LiteralPath $outMd -Encoding UTF8
Write-MigLog "Wrote $outMd"
if ($fail -gt 0) { Write-MigLog "VERIFY FAILED ($fail)" 'ERROR'; exit 1 }
Write-MigLog "VERIFY OK"
exit 0
