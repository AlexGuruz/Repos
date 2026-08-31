<#
.SYNOPSIS
  Smoke checks for Kylo/Greg on power-1 after hard cut.
#>
param()
$ErrorActionPreference = 'Continue'

$layout = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'layout.json') -Raw | ConvertFrom-Json
$junction = $layout.power1.kylo_junction
$target = $layout.power1.kylo_target
$greg = $layout.power1.greg_root
$fail = 0

function Ok($msg) { Write-Host "[PASS] $msg" -ForegroundColor Green }
function Bad($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red; $script:fail++ }
function Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }

if (Test-Path -LiteralPath $junction) { Ok "Junction exists: $junction" } else { Bad "Junction missing: $junction" }
if (Test-Path -LiteralPath $target) { Ok "Target exists: $target" } else { Bad "Target missing: $target" }
if (Test-Path -LiteralPath $greg) { Ok "Greg root: $greg" } else { Warn "Greg root missing: $greg" }

$hb = Join-Path $junction '.kylo\instances\KYLO_2026\health\heartbeat.json'
if (Test-Path -LiteralPath $hb) {
    $age = (Get-Date) - (Get-Item -LiteralPath $hb).LastWriteTime
    if ($age.TotalMinutes -lt 30) { Ok "Heartbeat fresh ($([int]$age.TotalMinutes)m)" }
    else { Warn "Heartbeat stale ($([int]$age.TotalMinutes)m): $hb" }
} else {
    Warn "No KYLO_2026 heartbeat at $hb"
}

# Ports
foreach ($port in @(5433, 5434, 8765, 5678)) {
    try {
        $c = Test-NetConnection -ComputerName 127.0.0.1 -Port $port -WarningAction SilentlyContinue
        if ($c.TcpTestSucceeded) { Ok "Port $port open" } else { Warn "Port $port closed" }
    } catch { Warn "Port $port check failed" }
}

# Docker watcher mount hint
try {
    $mounts = docker inspect kylo-watcher-2026 --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}; {{end}}' 2>$null
    if ($mounts) {
        if ($mounts -match 'products\\project-kylo|products/project-kylo|Project-Kylo') {
            Ok "Watcher mounts: $mounts"
        } else {
            Warn "Watcher mounts unexpected: $mounts"
        }
    } else {
        Warn "Container kylo-watcher-2026 not found or docker unavailable"
    }
} catch { Warn "docker inspect failed" }

if ($fail -gt 0) { Write-Host "SMOKE FAILED ($fail)" -ForegroundColor Red; exit 1 }
Write-Host "SMOKE OK" -ForegroundColor Green
exit 0
