# pull_telemetry.ps1 - Pull telemetry from oldrig to vault
# Logs to: C:\worker\logs\phase2_newrig.log

$logPath = 'C:\worker\logs\phase2_newrig.log'
$remoteFile = 'C:\worker\logs\telemetry\oldrig_status.md'
$vaultFile = 'E:\Repos\Ai\Obsidian\Brain\_ops\telemetry\oldrig_status.md'

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $logMessage = "[$timestamp] $Message"
    Add-Content -Path $logPath -Value $logMessage
    Write-Host $logMessage
}

Write-Log "=== Pull Telemetry from Oldrig ==="
Write-Log "Remote file: $remoteFile"
Write-Log "Vault destination: $vaultFile"

try {
    # Read file from oldrig via SSH
    Write-Log "Reading telemetry file from oldrig..."
    $tempFile = Join-Path $env:TEMP "oldrig_status_$(Get-Date -Format 'yyyyMMdd_HHmmss').md"
    
    $sshCommand = "powershell -NoProfile -Command `"Get-Content -Path '$remoteFile' -Raw -ErrorAction Stop`""
    $sshOutput = ssh oldrig $sshCommand 2>&1
    $sshExitCode = $LASTEXITCODE
    
    if ($sshExitCode -ne 0) {
        throw "SSH command failed with exit code $sshExitCode. Output: $sshOutput"
    }
    
    if ([string]::IsNullOrWhiteSpace($sshOutput)) {
        throw "Telemetry file appears to be empty or could not be read"
    }
    
    Write-Log "Successfully read telemetry file (length: $($sshOutput.Length) characters)"
    
    # Save to temp file first
    Write-Log "Saving to temp file: $tempFile"
    Set-Content -Path $tempFile -Value $sshOutput -Encoding UTF8 -ErrorAction Stop
    Write-Log "Temp file saved successfully"
    
    # Copy to vault
    Write-Log "Copying to vault: $vaultFile"
    $vaultDir = Split-Path -Path $vaultFile -Parent
    if (-not (Test-Path $vaultDir)) {
        Write-Log "Creating vault directory: $vaultDir"
        New-Item -ItemType Directory -Path $vaultDir -Force | Out-Null
    }
    
    Set-Content -Path $vaultFile -Value $sshOutput -Encoding UTF8 -ErrorAction Stop
    Write-Log "Vault file updated successfully"
    
    # Clean up temp file
    if (Test-Path $tempFile) {
        Remove-Item -Path $tempFile -Force -ErrorAction SilentlyContinue
        Write-Log "Temp file cleaned up"
    }
    
    Write-Log "=== Telemetry Pull Complete ==="
    exit 0
    
} catch {
    Write-Log "ERROR: $($_.Exception.Message)"
    Write-Log "Stack trace: $($_.ScriptStackTrace)"
    exit 1
}
