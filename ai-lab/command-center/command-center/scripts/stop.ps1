# AI Lab Command Center - stop frontend + backend (Windows)
# Kills processes listening on Vite (5173) and Uvicorn (8000) by default.
param(
    [int[]]$Ports = @(8000, 5173)
)

Write-Host ""
Write-Host "  Stopping Command Center listeners..." -ForegroundColor Cyan

foreach ($port in $Ports) {
    try {
        $pids = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
    } catch {
        $pids = @()
    }
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

Write-Host "  Done (ports: $($Ports -join ', '))." -ForegroundColor Green
Write-Host ""
