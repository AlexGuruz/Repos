# Run git after removing stale index.lock. Use when "Unable to create index.lock" blocks add/commit.
# Usage from E:\Repos: .\git_no_lock.ps1 add Growflow/
#                      .\git_no_lock.ps1 commit -m "Batch 2: Growflow"
$lock = Join-Path (Get-Location) ".git\index.lock"
if (Test-Path $lock) { Remove-Item -Force $lock }
& git @args
