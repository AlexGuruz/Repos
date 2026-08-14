<#
.SYNOPSIS
  Generate Repos.code-workspace from layout.json (products + docs + tools/migration).
#>
param(
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib\Layout.ps1"

$root = Get-ReposRoot
$layout = Get-MigrationLayout
$folders = @()
$folders += @{ name = 'Repos (root)'; path = '.' }
$folders += @{ name = 'docs'; path = 'docs' }
$folders += @{ name = 'migration'; path = 'tools/migration' }

$status = Get-LayoutStatus
if ($status -eq 'migrated') {
    foreach ($m in $layout.moves) {
        if ($m.status -eq 'production') {
            $folders += @{ name = $m.id; path = ($m.to -replace '\\', '/') }
        }
    }
} else {
    foreach ($m in $layout.moves) {
        if ($m.status -eq 'production') {
            $folders += @{ name = $m.id; path = $m.from }
        }
    }
}

$ws = [ordered]@{
    folders = @($folders | ForEach-Object { [ordered]@{ name = $_.name; path = $_.path } })
    settings = [ordered]@{
        'files.exclude' = [ordered]@{
            '**/node_modules' = $true
            '**/__pycache__' = $true
            'vendor' = $true
            'archive' = $true
            'tools/winpython' = $true
            'tools/venv' = $true
        }
    }
}

$json = $ws | ConvertTo-Json -Depth 6
$out = Join-Path $root 'Repos.code-workspace'
$stamp = New-ReportStamp
$preview = Join-Path (Get-ReportsDir) "workspace-$stamp.code-workspace"
Set-Content -LiteralPath $preview -Value $json -Encoding UTF8
Write-MigLog "Preview: $preview"
if ($Apply) {
    if (Test-Path $out) {
        Copy-Item -LiteralPath $out -Destination (Join-Path (Get-ReportsDir) "Repos.code-workspace.bak.$stamp") -Force
    }
    Set-Content -LiteralPath $out -Value $json -Encoding UTF8
    Write-MigLog "Wrote $out"
} else {
    Write-MigLog "Dry-run only (pass -Apply to write Repos.code-workspace)" 'WARN'
}
