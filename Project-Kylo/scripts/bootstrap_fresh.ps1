# Bootstrap Project-Kylo on a fresh rig
# Run AFTER Docker services are up (Postgres must be running)
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path "$RepoRoot\db")) { $RepoRoot = $PSScriptRoot }
$dbPath = Join-Path $RepoRoot "db\ddl"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Bootstrap Kylo Database (Fresh Rig)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Wait for Postgres
Write-Host "Waiting for Postgres..." -ForegroundColor Yellow
$maxWait = 30
$waited = 0
while ($waited -lt $maxWait) {
    $r = docker exec kylo-pg psql -U postgres -c "SELECT 1" 2>&1
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 2
    $waited += 2
}
if ($waited -ge $maxWait) {
    Write-Host "Postgres not ready. Start Docker first: .\start_all_services.ps1" -ForegroundColor Red
    exit 1
}
Write-Host "Postgres ready" -ForegroundColor Green

# Create kylo_global
docker exec kylo-pg psql -U postgres -c "SELECT 1 FROM pg_database WHERE datname='kylo_global'" -t 2>$null | Out-Null
$exists = docker exec kylo-pg psql -U postgres -t -c "SELECT 1 FROM pg_database WHERE datname='kylo_global'" 2>$null
if (-not $exists -or $exists.Trim() -eq "") {
    Write-Host "Creating database kylo_global..." -ForegroundColor Yellow
    docker exec kylo-pg createdb -U postgres kylo_global
    Write-Host "Created kylo_global" -ForegroundColor Green
} else {
    Write-Host "Database kylo_global already exists" -ForegroundColor Gray
}

# Apply global DDL (order matters)
$globalDDL = @(
    "0001_rules.sql", "0002_global_two_phase.sql", "0003_helpers.sql",
    "0004_control_rules_version.sql", "0005_control_mover_runs.sql",
    "0006_rules_version_checksum.sql", "0006_control_mover_runs_migration.sql",
    "0007_control_migrations_and_rules_snapshots.sql", "0008_csv_intake_deduplication.sql",
    "0011_app_pending_txns.sql", "0012_control_sheet_posts.sql",
    "0013_control_triage_metrics.sql", "0014_control_sheet_posts_unique.sql",
    "0015_control_company_config.sql"
)
foreach ($f in $globalDDL) {
    $p = Join-Path $dbPath $f
    if (Test-Path $p) {
        Write-Host "Applying $f..." -ForegroundColor Gray
        Get-Content $p -Raw | docker exec -i kylo-pg psql -U postgres -d kylo_global -v ON_ERROR_STOP=1 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Host "  (may already be applied)" -ForegroundColor DarkGray }
    }
}

# Create company DBs and apply company DDL
$companies = @("nugz", "710", "puffin", "jgd")  # kylo_nugz, kylo_710, kylo_puffin, kylo_jgd
foreach ($c in $companies) {
    $dbName = "kylo_$c"
    $exists = docker exec kylo-pg psql -U postgres -t -c "SELECT 1 FROM pg_database WHERE datname='$dbName'" 2>$null
    if (-not $exists -or $exists.Trim() -eq "") {
        Write-Host "Creating $dbName..." -ForegroundColor Yellow
        docker exec kylo-pg createdb -U postgres $dbName
    }
    foreach ($cf in @("company_0001_app.sql", "company_0002_rules_hash.sql", "company_0003_rules_snapshot_apply.sql")) {
        $p = Join-Path $dbPath $cf
        if (Test-Path $p) {
            Get-Content $p -Raw | docker exec -i kylo-pg psql -U postgres -d $dbName -v ON_ERROR_STOP=1 2>&1 | Out-Null
        }
    }
}

Write-Host ""
Write-Host "Bootstrap complete!" -ForegroundColor Green
