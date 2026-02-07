<#
.SYNOPSIS
  Install Obsidian community plugins from GitHub releases.
.DESCRIPTION
  Downloads latest releases of specified plugins and extracts to .obsidian/plugins/.
  Creates community-plugins.json with enabled plugin IDs.
.PARAMETER VaultPath
  Path to Obsidian vault (default: E:\Repos\Ai\Obsidian\Brain)
#>
param(
    [string]$VaultPath = "E:\Repos\Ai\Obsidian\Brain"
)

$ErrorActionPreference = "Stop"
$PluginsDir = Join-Path $VaultPath ".obsidian\plugins"
$CommunityPluginsJson = Join-Path $VaultPath ".obsidian\community-plugins.json"

$PluginRoster = @(
    @{ id = "dataview"; repo = "blacksmithgu/obsidian-dataview" },
    @{ id = "breadcrumbs"; repo = "SkepticMystic/breadcrumbs" },
    @{ id = "obsidian-git"; repo = "denolehov/obsidian-git" },
    @{ id = "table-editor-obsidian"; repo = "tgrosinger/advanced-tables-obsidian" },
    @{ id = "tag-wrangler"; repo = "pjeby/tag-wrangler" },
    @{ id = "buttons"; repo = "shabegom/buttons" },
    @{ id = "graph-analysis"; repo = "SkepticMystic/graph-analysis" },
    @{ id = "omnisearch"; repo = "scambier/obsidian-omnisearch" },
    @{ id = "templater-obsidian"; repo = "SilentVoid13/Templater" },
    @{ id = "obsidian-shellcommands"; repo = "Taitava/obsidian-shellcommands" }
)

if (-not (Test-Path $VaultPath)) {
    throw "Vault not found: $VaultPath"
}

if (-not (Test-Path (Join-Path $VaultPath ".obsidian"))) {
    throw "Not an Obsidian vault (.obsidian folder missing). Enable Community plugins first: Settings > Community plugins > Turn on."
}

New-Item -ItemType Directory -Path $PluginsDir -Force | Out-Null

$installed = 0
foreach ($p in $PluginRoster) {
    $id = $p.id
    $repo = $p.repo
    $destDir = Join-Path $PluginsDir $id
    New-Item -ItemType Directory -Path $destDir -Force | Out-Null

    try {
        $apiUrl = "https://api.github.com/repos/$repo/releases/latest"
        $release = Invoke-RestMethod -Uri $apiUrl -Headers @{ "User-Agent" = "Obsidian-Plugin-Installer" }

        $zipAsset = $release.assets | Where-Object { $_.name -match '\.zip$' } | Select-Object -First 1
        if ($zipAsset) {
            $zipPath = Join-Path $env:TEMP "obsidian-$id.zip"
            Invoke-WebRequest -Uri $zipAsset.browser_download_url -OutFile $zipPath -UseBasicParsing
            Expand-Archive -Path $zipPath -DestinationPath $destDir -Force
            Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
            $rootFiles = Get-ChildItem $destDir -File
            $innerDirs = Get-ChildItem $destDir -Directory
            if ($rootFiles.Count -eq 0 -and $innerDirs.Count -eq 1) {
                Get-ChildItem $innerDirs[0].FullName -File | Move-Item -Destination $destDir -Force
                Remove-Item $innerDirs[0].FullName -Recurse -Force -ErrorAction SilentlyContinue
            }
        } else {
            $baseUrl = $release.assets[0].browser_download_url -replace '[^/]+$', ''
            foreach ($name in @("main.js", "manifest.json", "styles.css")) {
                $asset = $release.assets | Where-Object { $_.name -eq $name } | Select-Object -First 1
                if ($asset) {
                    $destFile = Join-Path $destDir $name
                    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $destFile -UseBasicParsing
                }
            }
            if (-not (Test-Path (Join-Path $destDir "main.js"))) {
                throw "main.js not found after download"
            }
        }

        Write-Host "[OK] $id"
        $installed++
    } catch {
        Write-Warning "Failed $id : $_"
    }
}

$existing = @{}
if (Test-Path $CommunityPluginsJson) {
    try {
        $obj = Get-Content $CommunityPluginsJson -Raw | ConvertFrom-Json
        $obj.PSObject.Properties | ForEach-Object { $existing[$_.Name] = $_.Value }
    } catch { }
}
foreach ($p in $PluginRoster) {
    $existing[$p.id] = $true
}
$entries = $existing.GetEnumerator() | Sort-Object Name | ForEach-Object { "  `"$($_.Key)`": $($_.Value.ToString().ToLower())" }
$jsonContent = "{" + "`n" + ($entries -join ",`n") + "`n}"
[System.IO.File]::WriteAllText($CommunityPluginsJson, $jsonContent, [System.Text.UTF8Encoding]::new($false))

Write-Host "`nInstalled $installed plugins. Restart Obsidian to load."
