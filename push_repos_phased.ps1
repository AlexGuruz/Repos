# Push each project folder under E:\Repos as its own GitHub repo, one at a time.
# - Creates the repo on GitHub (via gh CLI or instructions)
# - Inits git in the folder if needed, then push
# Run from E:\Repos: .\push_repos_phased.ps1
#   .\push_repos_phased.ps1 -GitHubOrg AlexGuruz
#   .\push_repos_phased.ps1 -DryRun
# Optional: -DryRun (list only)  -ListFile path  -GitHubOrg org-or-username

param(
    [switch]$DryRun,
    [string]$ListFile = "repos_to_push.txt",
    [string]$GitHubOrg = ""
)

$ErrorActionPreference = "Stop"
$ReposRoot = $PSScriptRoot
$PostBufferBytes = 524288000  # 500 MB

# Sanitize folder name for GitHub repo name (spaces -> -, only drop invalid chars)
function Get-RepoName($folderName) {
    $name = $folderName.Trim() -replace '\s+', '-'
    $name = $name -replace '[^\w.\-]', ''   # keep letters, digits, underscore, dot, hyphen
    if ([string]::IsNullOrWhiteSpace($name)) { $name = "repo-$([guid]::NewGuid().ToString('N').Substring(0,8))" }
    return $name
}

# Load project folder list
$listPath = Join-Path $ReposRoot $ListFile
$projectFolders = @()
if (Test-Path $listPath) {
    $projectFolders = Get-Content $listPath | Where-Object { $_ -match '^\s*[^#]' } | ForEach-Object { $_.Trim() } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
}
if ($projectFolders.Count -eq 0) {
    Write-Host "No folders in list. Add folder names to $ListFile (one per line)." -ForegroundColor Yellow
    exit 0
}

# Resolve to full paths; skip missing
$projects = @()
foreach ($name in $projectFolders) {
    $fullPath = Join-Path $ReposRoot $name
    if (-not (Test-Path $fullPath -PathType Container)) {
        Write-Host "Skip (not found): $name" -ForegroundColor Gray
        continue
    }
    $projects += @{ FolderName = $name; Path = $fullPath; RepoName = Get-RepoName $name }
}

if ($projects.Count -eq 0) {
    Write-Host "No valid project folders to push." -ForegroundColor Yellow
    exit 0
}

Write-Host "Found $($projects.Count) project(s). Each will be its own GitHub repo, pushed one at a time.`n" -ForegroundColor Cyan

$useGh = $false
try { if (Get-Command gh -ErrorAction SilentlyContinue) { $useGh = $true } } catch {}
if (-not $useGh -and -not $DryRun) {
    Write-Host "Tip: Install GitHub CLI (gh) so this script can create repos. Otherwise create each repo in GitHub first.`n" -ForegroundColor Yellow
}

$i = 0
foreach ($proj in $projects) {
    $i++
    $dir = $proj.Path
    $folderName = $proj.FolderName
    $repoName = $proj.RepoName
    $repoSpec = if ($GitHubOrg) { "$GitHubOrg/$repoName" } else { $repoName }

    Write-Host "[$i/$($projects.Count)] $folderName -> GitHub repo: $repoSpec" -ForegroundColor Cyan
    Set-Location $dir
    if (-not $DryRun) { git config --global --add safe.directory $dir.Replace('\', '/') 2>$null }

    $hasGit = Test-Path (Join-Path $dir ".git") -PathType Container
    $remoteUrl = $null
    try { $remoteUrl = (git remote get-url origin 2>$null) } catch {}

    if ($DryRun) {
        if ($hasGit) { git remote -v 2>$null } else { Write-Host "  (no .git yet)" }
        Write-Host "  (dry run - no init/create/push)`n"
        continue
    }

    # Ensure git repo
    if (-not $hasGit) {
        Write-Host "  Initializing git..."
        git init
        try { git add -A 2>&1 | Out-Null } catch {}
        $addExit = $LASTEXITCODE
        $status = git status --porcelain 2>$null
        if ($status) {
            git commit -m "Initial commit"
        } else {
            Write-Host "  No files to commit; creating empty initial commit."
            git commit --allow-empty -m "Initial commit"
        }
    }

    git config http.postBuffer $PostBufferBytes 2>$null

    # Push to OUR repo (GitHubOrg/repoName). Create on GitHub if missing or if current origin is someone else's.
    $ourRepoUrl = "https://github.com/$repoSpec.git"
    $originIsOurs = $remoteUrl -and ($remoteUrl -match [regex]::Escape($repoSpec))
    if (-not $originIsOurs) {
        if ($useGh) {
            Write-Host "  Creating GitHub repo $repoSpec..."
            try { $null = & gh repo create $repoSpec --private --description "Pushed from Repos: $folderName" 2>&1 } catch {}
            if ($LASTEXITCODE -ne 0) { Write-Host "  (repo may already exist)" -ForegroundColor Gray }
            git remote set-url origin $ourRepoUrl 2>$null
            if ($LASTEXITCODE -ne 0) { git remote add origin $ourRepoUrl }
        } elseif ($GitHubOrg) {
            git remote set-url origin $ourRepoUrl 2>$null
            if ($LASTEXITCODE -ne 0) { git remote add origin $ourRepoUrl }
            Write-Host "  Set origin to $ourRepoUrl (create repo on GitHub if it doesn't exist)." -ForegroundColor Gray
        } else {
            Write-Host "  No remote or not our repo. Create repo '$repoSpec' on GitHub, then: git remote add origin $ourRepoUrl" -ForegroundColor Yellow
            continue
        }
    }

    Write-Host "  Pushing..."
    $branch = (git rev-parse --abbrev-ref HEAD 2>$null)
    if (-not $branch) { $branch = "main" }
    $pushExit = 0
    try {
        $pushOut = & git push -u origin $branch 2>&1
        $pushExit = $LASTEXITCODE
    } catch {
        $pushExit = 1
        $pushOut = $_.ToString()
    }
    if ($pushExit -ne 0) {
        Write-Host $pushOut -ForegroundColor Red
        Write-Host "  Push failed. Fix and re-run script.`n" -ForegroundColor Yellow
    } else {
        Write-Host "  Done.`n" -ForegroundColor Green
    }
}

Set-Location $ReposRoot
Write-Host "Phased push finished." -ForegroundColor Cyan
