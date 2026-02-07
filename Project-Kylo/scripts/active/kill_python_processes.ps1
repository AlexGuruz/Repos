# Script to kill Python processes on the system
# Use with caution - this will kill ALL Python processes unless filtered

param(
    [switch]$Force,  # Skip confirmation prompt
    [switch]$KyloOnly,  # Only kill Kylo-related Python processes (watcher, server, consumers)
    [switch]$ShowOnly  # Just show what would be killed, don't actually kill
)

Write-Host "=== Python Process Killer ===" -ForegroundColor Cyan
Write-Host ""

# Safety default: if not specified, only target Kylo processes.
if (-not $PSBoundParameters.ContainsKey('KyloOnly')) {
    $KyloOnly = $true
}

# Get all Python processes
$allPythonProcesses = Get-Process python -ErrorAction SilentlyContinue

if (-not $allPythonProcesses) {
    Write-Host "No Python processes found." -ForegroundColor Green
    exit 0
}

Write-Host "Found $($allPythonProcesses.Count) Python process(es):" -ForegroundColor Yellow
Write-Host ""

$processesToKill = @()

foreach ($proc in $allPythonProcesses) {
    $cmdLine = $null
    $isKyloRelated = $false
    
    try {
        $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($proc.Id)").CommandLine
        if ($cmdLine) {
            # Exclude common editor tooling (Cursor/VSCode Python extensions)
            if ($cmdLine -like "*\\.cursor\\extensions\\*" -or
                $cmdLine -like "*\\vscode\\extensions\\*" -or
                $cmdLine -like "*lsp_server.py*" -or
                $cmdLine -like "*pyright-langserver*" -or
                $cmdLine -like "*pylance*" -or
                $cmdLine -like "*debugpy*") {
                $isKyloRelated = $false
            } else {
                # Check for explicit Kylo commands (avoid matching just the interpreter path)
                if ($cmdLine -like "*-m bin.watch_all*" -or
                    $cmdLine -like "*\\bin\\watch_all.py*" -or
                    $cmdLine -like "*\\bin\\sort_and_post_from_jgdtruth.py*" -or
                    $cmdLine -like "*-m bin.sort_and_post_from_jgdtruth*" -or
                    $cmdLine -like "*uvicorn*scripts.server:app*" -or
                    $cmdLine -like "*scripts\\server.py*" -or
                    $cmdLine -like "*kafka_consumer_txns*" -or
                    $cmdLine -like "*kafka_consumer_promote*" -or
                    $cmdLine -like "*services\\bus\\kafka_consumer*") {
                    $isKyloRelated = $true
                }
            }
        }
    } catch {
        # Couldn't get command line
    }
    
    $processInfo = [PSCustomObject]@{
        PID = $proc.Id
        Name = $proc.ProcessName
        CommandLine = if ($cmdLine) { $cmdLine.Substring(0, [Math]::Min(100, $cmdLine.Length)) } else { "Unknown" }
        IsKyloRelated = $isKyloRelated
    }
    
    # Filter based on mode
    if ($KyloOnly) {
        if ($isKyloRelated) {
            $processesToKill += $processInfo
            Write-Host "  [KILL] PID $($proc.Id) - Kylo-related" -ForegroundColor Red
            if ($cmdLine) {
                Write-Host "         $($cmdLine.Substring(0, [Math]::Min(150, $cmdLine.Length)))" -ForegroundColor Gray
            }
        } else {
            Write-Host "  [SKIP] PID $($proc.Id) - Not Kylo-related" -ForegroundColor Gray
            if ($cmdLine) {
                Write-Host "         $($cmdLine.Substring(0, [Math]::Min(150, $cmdLine.Length)))" -ForegroundColor DarkGray
            }
        }
    } else {
        $processesToKill += $processInfo
        $color = if ($isKyloRelated) { "Red" } else { "Yellow" }
        $label = if ($isKyloRelated) { "Kylo-related" } else { "Other" }
        Write-Host "  [KILL] PID $($proc.Id) - $label" -ForegroundColor $color
        if ($cmdLine) {
            Write-Host "         $($cmdLine.Substring(0, [Math]::Min(150, $cmdLine.Length)))" -ForegroundColor Gray
        }
    }
}

Write-Host ""

if ($processesToKill.Count -eq 0) {
    Write-Host "No processes to kill." -ForegroundColor Green
    exit 0
}

if ($ShowOnly) {
    Write-Host "Show-only mode: Not killing any processes." -ForegroundColor Yellow
    exit 0
}

# Confirmation
if (-not $Force) {
    Write-Host "About to kill $($processesToKill.Count) Python process(es)." -ForegroundColor Yellow
    $confirm = Read-Host "Continue? (y/N)"
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-Host "Cancelled." -ForegroundColor Gray
        exit 0
    }
}

# Kill processes
Write-Host ""
Write-Host "Killing processes..." -ForegroundColor Yellow

$killed = 0
$failed = 0

foreach ($procInfo in $processesToKill) {
    try {
        Stop-Process -Id $procInfo.PID -Force -ErrorAction Stop
        Write-Host "  [OK] Killed PID $($procInfo.PID)" -ForegroundColor Green
        $killed++
    } catch {
        Write-Host "  [FAIL] Failed to kill PID $($procInfo.PID): $($_.Exception.Message)" -ForegroundColor Red
        $failed++
    }
}

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan
Write-Host "  Killed: $killed" -ForegroundColor Green
if ($failed -gt 0) {
    Write-Host "  Failed: $failed" -ForegroundColor Red
} else {
    Write-Host "  Failed: $failed" -ForegroundColor Gray
}
Write-Host ""

