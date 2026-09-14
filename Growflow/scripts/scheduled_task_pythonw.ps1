$ErrorActionPreference = "Stop"

function Join-GrowflowTaskArgument {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Parts
    )

    $quoted = foreach ($part in $Parts) {
        '"' + $part.Replace('"', '\"') + '"'
    }

    return ($quoted -join " ")
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
    $helper = Join-Path $resolvedRoot.Path "scripts\invoke_python_hidden.ps1"
    if (-not (Test-Path $helper)) {
        throw "Scheduled task helper not found: $helper"
    }

    $argumentParts = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-WindowStyle",
        "Hidden",
        "-File",
        $helper,
        $RelativeScript
    ) + @($ScriptArgs)

    return New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument (Join-GrowflowTaskArgument -Parts $argumentParts) `
        -WorkingDirectory $resolvedRoot.Path
}
