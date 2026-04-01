# Setup main rig: install Cursor rules from ai-lab-governance and set env
# Run from repo root or set $GovernanceRoot
# Usage: .\setup_main_rig.ps1 [-GovernanceRoot "E:\Repos\ai-lab-governance"]

param(
    [string]$GovernanceRoot = $env:AI_LAB_GOVERNANCE_ROOT
)

if (-not $GovernanceRoot) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $GovernanceRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
}

$cursorRulesSource = Join-Path $GovernanceRoot "cursor"
$cursorUser = $env:USERPROFILE
$cursorRulesDest = Join-Path $cursorUser ".cursor" "rules"

if (-not (Test-Path $cursorRulesSource)) {
    Write-Error "Governance cursor path not found: $cursorRulesSource"
    exit 1
}

New-Item -ItemType Directory -Force -Path $cursorRulesDest | Out-Null

# Copy shared rule file so Cursor picks it up
$ruleFile = Join-Path $cursorRulesSource "cursor_rules.md"
if (Test-Path $ruleFile) {
    Copy-Item -Path $ruleFile -Destination (Join-Path $cursorRulesDest "governance.md") -Force
    Write-Host "Installed Cursor rule: governance.md"
}

# Prompts: copy to a known location (Cursor may use different prompt storage; document for manual copy if needed)
$promptsSource = Join-Path $cursorRulesSource "prompts"
$promptsDest = Join-Path $cursorUser ".cursor" "governance-prompts"
if (Test-Path $promptsSource) {
    New-Item -ItemType Directory -Force -Path $promptsDest | Out-Null
    Copy-Item -Path (Join-Path $promptsSource "*") -Destination $promptsDest -Force -Recurse
    Write-Host "Installed prompts to: $promptsDest"
}

# Persist governance root for this user (PowerShell profile or system env)
Write-Host "Set AI_LAB_GOVERNANCE_ROOT for this session: $GovernanceRoot"
$env:AI_LAB_GOVERNANCE_ROOT = $GovernanceRoot
Write-Host "To make permanent, add to your profile: `$env:AI_LAB_GOVERNANCE_ROOT = '$GovernanceRoot'"

# Verify
$verifyScript = Join-Path $GovernanceRoot "bootstrap" "verify_governance.py"
if (Test-Path $verifyScript) {
    & python $verifyScript
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Main rig setup done. Use same repo path on worker and run setup_worker_rig.ps1 or setup_worker_rig.sh there."
