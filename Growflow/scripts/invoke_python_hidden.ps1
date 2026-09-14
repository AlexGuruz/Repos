param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PythonArgs
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")

$candidates = @(
    (Join-Path $root ".venv\Scripts\python.exe"),
    (Join-Path $root "venv\Scripts\python.exe"),
    "python.exe",
    "python"
)

$python = $null
foreach ($candidate in $candidates) {
    if ($candidate -like "*\*") {
        if (Test-Path $candidate) {
            $python = $candidate
            break
        }
    }
    else {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) {
            $python = $cmd.Source
            break
        }
    }
}

if (-not $python) {
    throw "Could not find python executable for Growflow hidden runner"
}

$env:PYTHONPATH = $root.Path
$proc = Start-Process `
    -FilePath $python `
    -ArgumentList $PythonArgs `
    -WorkingDirectory $root.Path `
    -WindowStyle Hidden `
    -Wait `
    -PassThru

exit $proc.ExitCode
