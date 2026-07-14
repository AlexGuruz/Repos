# Shared Scheduled Task action builder for hidden Growflow Python jobs.
$ErrorActionPreference = "Stop"

function Quote-GrowflowTaskArgument {
    param([Parameter(Mandatory = $true)][string]$Value)

    if ($Value -match '[\s"]') {
        return '"' + ($Value -replace '"', '`"') + '"'
    }
    return $Value
}

function New-GrowflowPythonwTaskAction {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,

        [Parameter(Mandatory = $true)]
        [string]$RelativeScript,

        [string[]]$ScriptArgs = @()
    )

    $resolvedRoot = Resolve-Path $Root
    $runner = Join-Path $PSScriptRoot "invoke_python_hidden.ps1"
    $script = Join-Path $resolvedRoot $RelativeScript

    if (-not (Test-Path $runner)) {
        throw "Missing hidden Python runner: $runner"
    }
    if (-not (Test-Path $script)) {
        throw "Missing Python script: $script"
    }

    $runnerArg = Quote-GrowflowTaskArgument $runner
    $scriptArg = Quote-GrowflowTaskArgument $RelativeScript
    $extraArgs = @($ScriptArgs | ForEach-Object { Quote-GrowflowTaskArgument $_ })
    $argList = @(
        "-WindowStyle Hidden",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy Bypass",
        "-File $runnerArg",
        $scriptArg
    ) + $extraArgs

    return New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument ($argList -join " ") `
        -WorkingDirectory $resolvedRoot.Path
}
