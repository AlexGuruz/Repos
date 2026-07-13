function Quote-TaskArgument {
    param([Parameter(Mandatory = $true)][string]$Value)
    return '"' + ($Value -replace '"', '\"') + '"'
}

function New-GrowflowPythonwTaskAction {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,

        [Parameter(Mandatory = $true)]
        [string]$RelativeScript,

        [string[]]$ScriptArgs = @()
    )

    $helper = Join-Path $PSScriptRoot "invoke_python_hidden.ps1"
    if (-not (Test-Path $helper)) {
        throw "Missing helper script: $helper"
    }

    $scriptPath = Join-Path $Root $RelativeScript
    if (-not (Test-Path $scriptPath)) {
        throw "Missing Python script: $scriptPath"
    }

    $allArgs = @(
        "-WindowStyle",
        "Hidden",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        (Quote-TaskArgument $helper),
        (Quote-TaskArgument $RelativeScript)
    ) + $ScriptArgs

    return New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument ($allArgs -join " ") `
        -WorkingDirectory $Root
}
