# AI Lab Command Center - stop frontend + backend (Windows)
# Kills processes listening on Vite (5173) and Uvicorn (8000) by default,
# plus any stray `uvicorn main:app` / vite processes from failed restarts.
param(
    [int[]]$Ports = @(8000, 5173)
)

function Get-ListenerPidsForPort {
    param([int]$Port)
    $set = [System.Collections.Generic.HashSet[int]]::new()
    try {
        Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            ForEach-Object { if ($_.OwningProcess) { [void]$set.Add([int]$_.OwningProcess) } }
    } catch {}
    foreach ($line in (netstat -ano 2>$null)) {
        if ($line -match ":$Port\s+.*LISTENING\s+(\d+)\s*$") {
            [void]$set.Add([int]$Matches[1])
        }
    }
    return @($set)
}

Write-Host ""
Write-Host "  Stopping Command Center listeners..." -ForegroundColor Cyan

foreach ($port in $Ports) {
    $pids = Get-ListenerPidsForPort -Port $port
    foreach ($procId in $pids) {
        if (-not $procId) { continue }
        try {
            $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($p) {
                Write-Host "  Port $port -> stop PID $procId ($($p.ProcessName))" -ForegroundColor Yellow
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        } catch {}
    }
}

# Stray workers that lost their socket but still burn CPU / confuse restarts.
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and (
            $_.CommandLine -match 'uvicorn.*main:app' -or
            $_.CommandLine -match 'vite' -and $_.CommandLine -match 'command-center\\frontend'
        )
    } |
    ForEach-Object {
        Write-Host "  Stray -> stop PID $($_.ProcessId)" -ForegroundColor Yellow
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Write-Host "  Done (ports: $($Ports -join ', '))." -ForegroundColor Green
Write-Host ""
