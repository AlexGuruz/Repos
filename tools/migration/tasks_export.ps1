<#
.SYNOPSIS
  Export scheduled tasks related to Growflow / ai-lab / Kylo before migration.
#>
param()
$ErrorActionPreference = 'Continue'
. "$PSScriptRoot\lib\Layout.ps1"

$stamp = New-ReportStamp
$outDir = Join-Path (Get-ReportsDir) "tasks-before-$stamp"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$patterns = @('Growflow', 'Kylo', 'ai-lab', 'prepared_context', 'PreparedContext', 'PettyCash', 'Retail')
$csv = Join-Path $outDir 'tasks.csv'

$all = schtasks /Query /FO CSV /V 2>$null | ConvertFrom-Csv
$matched = $all | Where-Object {
    $n = $_.'TaskName'
    foreach ($p in $patterns) { if ($n -like "*$p*") { return $true } }
    $false
}

$matched | Export-Csv -LiteralPath $csv -NoTypeInformation -Encoding UTF8
Write-MigLog "Exported $($matched.Count) tasks -> $csv"

foreach ($t in $matched) {
    $name = $t.'TaskName'
    $safe = ($name -replace '[\\/:*?"<>|]', '_').TrimStart('\')
    $xmlPath = Join-Path $outDir "$safe.xml"
    try {
        schtasks /Query /TN $name /XML 2>$null | Set-Content -LiteralPath $xmlPath -Encoding UTF8
    } catch { }
}

Write-MigLog "XML dump dir: $outDir"
Write-Output $outDir
