function Resolve-GrowflowPythonw {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    $candidates = @(
        (Join-Path $Root ".venv\Scripts\pythonw.exe"),
        (Join-Path $Root "venv\Scripts\pythonw.exe"),
        "pythonw.exe",
        "python.exe"
    )

    foreach ($candidate in $candidates) {
        if ($candidate -like "*\*") {
            if (Test-Path $candidate) { return $candidate }
        }
        else {
            $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
            if ($cmd) { return $cmd.Source }
        }
    }

    throw "Could not find pythonw.exe or python.exe for Growflow scheduled task"
}

function Join-GrowflowArgumentList {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativeScript,

        [string[]]$ScriptArgs = @()
    )

    $parts = @("`"$RelativeScript`"")
    foreach ($arg in $ScriptArgs) {
        $escaped = [string]$arg -replace '"', '\"'
        $parts += "`"$escaped`""
    }
    return ($parts -join " ")
}

function New-GrowflowPythonwTaskAction {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,

        [Parameter(Mandatory = $true)]
        [string]$RelativeScript,

        [string[]]$ScriptArgs = @()
    )

    $python = Resolve-GrowflowPythonw -Root $Root
    $arguments = Join-GrowflowArgumentList -RelativeScript $RelativeScript -ScriptArgs $ScriptArgs
    return New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory $Root
}
