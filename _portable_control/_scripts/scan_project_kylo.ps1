$Root = "D:\Project-Kylo"
$OutDir = "D:\_PORTABLE_CONTROL\_audit\project_kylo"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$InventoryCsv = Join-Path $OutDir "inventory_files.csv"
$TreeTxt      = Join-Path $OutDir "inventory_tree.txt"

# Exclusions (adjust if needed)
$ExcludeDirs = @(
  ".git",
  "node_modules",
  ".venv",
  "venv",
  "__pycache__",
  ".pytest_cache",
  ".mypy_cache",
  ".ruff_cache",
  ".idea",
  ".vscode",
  "dist",
  "build"
)

Write-Host "Scanning: $Root"
Write-Host "Output:   $OutDir"

# Get file inventory (read-only)
$files = Get-ChildItem -LiteralPath $Root -Recurse -File -Force -ErrorAction SilentlyContinue |
  Where-Object {
    $p = $_.FullName
    foreach ($d in $ExcludeDirs) {
      if ($p -match "\\$d\\") { return $false }
    }
    return $true
  } |
  Select-Object `
    @{Name="path"; Expression={$_.FullName}},
    @{Name="size_bytes"; Expression={$_.Length}},
    @{Name="modified_iso"; Expression={$_.LastWriteTimeUtc.ToString("s")}},
    @{Name="extension"; Expression={$_.Extension}}

$files | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $InventoryCsv

# Tree view (best effort)
cmd /c "tree `"$Root`" /F /A > `"$TreeTxt`""

Write-Host "Done."
Write-Host "Files CSV: $InventoryCsv"
Write-Host "Tree TXT:  $TreeTxt"
