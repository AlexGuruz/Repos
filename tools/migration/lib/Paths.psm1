# Paths.psm1 — PowerShell path API for senior layout (dual-read)
$ErrorActionPreference = 'Stop'

function Get-MigrationRoot {
    $here = $PSScriptRoot
    if (-not $here) { $here = Split-Path -Parent $MyInvocation.MyCommand.Path }
    return (Resolve-Path (Join-Path $here '..')).Path
}

function Get-LayoutObject {
    $layoutPath = Join-Path (Get-MigrationRoot) 'layout.json'
    if (-not (Test-Path -LiteralPath $layoutPath)) {
        throw "layout.json missing at $layoutPath"
    }
    return (Get-Content -LiteralPath $layoutPath -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Get-ReposRoot {
    if ($env:REPOS_ROOT -and (Test-Path -LiteralPath $env:REPOS_ROOT)) {
        return (Resolve-Path -LiteralPath $env:REPOS_ROOT).Path
    }
    if ($env:AI_LAB_REPOS_ROOT -and (Test-Path -LiteralPath $env:AI_LAB_REPOS_ROOT)) {
        return (Resolve-Path -LiteralPath $env:AI_LAB_REPOS_ROOT).Path
    }
    $mig = Get-MigrationRoot
    $candidate = (Resolve-Path (Join-Path $mig '..\..')).Path
    # tools/migration -> tools -> Repos
    if (Test-Path -LiteralPath (Join-Path $candidate 'tools\migration\layout.json')) {
        return $candidate
    }
    foreach ($g in @('E:\Repos', 'C:\Repos', 'C:\worker\repos')) {
        if (Test-Path -LiteralPath $g) { return $g }
    }
    throw 'REPOS_ROOT not found'
}

function Get-ProductPath {
    param(
        [Parameter(Mandatory = $true)][string]$Id
    )
    $root = Get-ReposRoot
    $layout = Get-LayoutObject
    $move = $layout.moves | Where-Object { $_.id -eq $Id } | Select-Object -First 1
    if ($move) {
        $newPath = Join-Path $root (($move.to -replace '/', '\'))
        if (Test-Path -LiteralPath $newPath) { return (Resolve-Path -LiteralPath $newPath).Path }
        $legacy = Join-Path $root $move.from
        if (Test-Path -LiteralPath $legacy) { return (Resolve-Path -LiteralPath $legacy).Path }
        return $newPath
    }
    $products = Join-Path $root 'products'
    foreach ($c in @((Join-Path $products $Id), (Join-Path $root $Id))) {
        if (Test-Path -LiteralPath $c) { return (Resolve-Path -LiteralPath $c).Path }
    }
    throw "Product not found: $Id"
}

function Get-KyloRoot {
    if (Test-Path -LiteralPath 'C:\Project-Kylo') {
        return (Resolve-Path -LiteralPath 'C:\Project-Kylo').Path
    }
    return Get-ProductPath -Id 'project-kylo'
}

function Get-LayoutStatus {
    $root = Get-ReposRoot
    if ((Test-Path (Join-Path $root 'products\project-kylo')) -or (Test-Path (Join-Path $root 'products\ai-lab'))) {
        return 'migrated'
    }
    if ((Test-Path (Join-Path $root 'Project-Kylo')) -or (Test-Path (Join-Path $root 'ai-lab'))) {
        return 'legacy'
    }
    return 'unknown'
}

Export-ModuleMember -Function Get-MigrationRoot, Get-LayoutObject, Get-ReposRoot, Get-ProductPath, Get-KyloRoot, Get-LayoutStatus
