<#
.SYNOPSIS
  On power-1: recreate C:\Project-Kylo junction to products\project-kylo after sync.
  Run remotely via existing SSH helpers, or locally on power-1.
#>
param(
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'

$layoutPath = Join-Path $PSScriptRoot 'layout.json'
$layout = Get-Content -LiteralPath $layoutPath -Raw | ConvertFrom-Json
$junction = $layout.power1.kylo_junction
$target = $layout.power1.kylo_target
$greg = $layout.power1.greg_root

Write-Host "Kylo junction: $junction -> $target"
Write-Host "Greg root: $greg"

if (-not (Test-Path -LiteralPath $target)) {
    Write-Host "ERROR: target missing: $target — sync products tree first" -ForegroundColor Red
    exit 1
}

if (-not $Apply) {
    Write-Host "Dry-run only. Pass -Apply to recreate junction."
    if (Test-Path -LiteralPath $junction) {
        cmd /c dir "$junction" | Select-Object -First 5
    }
    exit 0
}

if (Test-Path -LiteralPath $junction) {
    $item = Get-Item -LiteralPath $junction -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        cmd /c rmdir "$junction"
    } else {
        Write-Host "ERROR: $junction exists and is not a junction. Refusing to delete." -ForegroundColor Red
        exit 1
    }
}

cmd /c mklink /J "$junction" "$target"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Junction OK: $junction -> $target"
if (-not (Test-Path -LiteralPath $greg)) {
    Write-Host "WARN: Greg root missing: $greg" -ForegroundColor Yellow
}
exit 0
