param(
  [string]$ConnectionString = $env:DATABASE_URL,
  [string]$File = ""
)

if (-not $ConnectionString) { throw "Set DATABASE_URL or pass -ConnectionString" }

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($File -ne "") {
  $ddl = if (Test-Path $File) { Resolve-Path $File } else { Join-Path $root $File }
  if (-not (Test-Path $ddl)) { throw "DDL file not found: $File" }
  & psql "$ConnectionString" -v ON_ERROR_STOP=1 -f $ddl
} else {
  $ddl = Join-Path $root "ddl\0001_rules.sql"
  & psql "$ConnectionString" -v ON_ERROR_STOP=1 -f $ddl
}


