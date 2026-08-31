# Shows a Windows toast for company email digests.
# Prefer BurntToast if installed: Install-Module BurntToast -Scope CurrentUser
param(
    [Parameter(Mandatory = $true)]
    [string]$TitleFile,
    [Parameter(Mandatory = $true)]
    [string]$BodyFile
)

$ErrorActionPreference = "Stop"
$title = (Get-Content -LiteralPath $TitleFile -Raw -Encoding UTF8).Trim()
$body = (Get-Content -LiteralPath $BodyFile -Raw -Encoding UTF8).Trim()
if (-not $title) { $title = "Company email" }
if (-not $body) { $body = "(empty)" }

# Cap length for toast surfaces
if ($title.Length -gt 120) { $title = $title.Substring(0, 117) + "..." }
if ($body.Length -gt 800) { $body = $body.Substring(0, 797) + "..." }

$burnt = Get-Module -ListAvailable -Name BurntToast | Select-Object -First 1
if ($burnt) {
    Import-Module BurntToast -ErrorAction Stop
    New-BurntToastNotification -Text $title, $body
    Write-Output "ok=burnttoast"
    exit 0
}

# Fallback: balloon tip via NotifyIcon (works without BurntToast)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.Visible = $true
$notify.BalloonTipTitle = $title
$notify.BalloonTipText = $body
$notify.ShowBalloonTip(8000)
Start-Sleep -Seconds 9
$notify.Dispose()
Write-Output "ok=balloon"
exit 0
