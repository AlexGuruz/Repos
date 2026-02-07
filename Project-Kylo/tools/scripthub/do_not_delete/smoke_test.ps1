# Smoke test to verify all required files exist and imports compile

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptsDir = Join-Path $ScriptDir "scripts"
$SrcDir = Join-Path $ScriptDir "src"
$ConfigDir = Join-Path $ScriptDir "config"

Write-Host "ScriptHub DO NOT DELETE - Smoke Test"
Write-Host "=" * 50

$Errors = 0

# Check required directories
Write-Host "`nChecking directories..."
$RequiredDirs = @($ScriptsDir, $SrcDir, $ConfigDir)
foreach ($Dir in $RequiredDirs) {
    if (Test-Path $Dir) {
        Write-Host "  [OK] $Dir"
    } else {
        Write-Host "  [MISSING] $Dir" -ForegroundColor Red
        $Errors++
    }
}

# Check required scripts
Write-Host "`nChecking scripts..."
$RequiredScripts = @(
    "sync_bank.py",
    "sync_company_ids.py",
    "dynamic_columns_jgdtruth.py",
    "run_both_syncs.py",
    "server.py",
    "rule_loader_jgdtruth.py"
)
foreach ($Script in $RequiredScripts) {
    $ScriptPath = Join-Path $ScriptsDir $Script
    if (Test-Path $ScriptPath) {
        Write-Host "  [OK] $Script"
    } else {
        Write-Host "  [MISSING] $Script" -ForegroundColor Red
        $Errors++
    }
}

# Check source files
Write-Host "`nChecking source files..."
$RequiredSrc = @("gsheets.py", "rules.py")
foreach ($SrcFile in $RequiredSrc) {
    $SrcPath = Join-Path $SrcDir $SrcFile
    if (Test-Path $SrcPath) {
        Write-Host "  [OK] $SrcFile"
    } else {
        Write-Host "  [MISSING] $SrcFile" -ForegroundColor Red
        $Errors++
    }
}

# Check config file
Write-Host "`nChecking config files..."
$ConfigFile = Join-Path $ConfigDir "config.json"
if (Test-Path $ConfigFile) {
    Write-Host "  [OK] config.json"
} else {
    Write-Host "  [MISSING] config.json (may need to be created)" -ForegroundColor Yellow
}

# Try to compile imports
Write-Host "`nTesting imports..."
$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if ($PythonExe) {
    $env:PYTHONPATH = $ScriptDir
    Set-Location $ScriptsDir
    
    # Test src imports
    $ImportTest = @"
import sys
sys.path.insert(0, r'$ScriptDir')
try:
    from src.gsheets import load_cfg, svc_from_sa
    from src.rules import load_rules
    print('  [OK] src imports')
except Exception as e:
    print(f'  [FAIL] src imports: {e}')
    sys.exit(1)
"@
    
    $ImportTest | & $PythonExe
    if ($LASTEXITCODE -ne 0) {
        $Errors++
    }
} else {
    Write-Host "  [SKIP] Python not found, skipping import test" -ForegroundColor Yellow
}

# Summary
Write-Host "`n" + "=" * 50
if ($Errors -eq 0) {
    Write-Host "Smoke test PASSED" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Smoke test FAILED ($Errors errors)" -ForegroundColor Red
    exit 1
}
