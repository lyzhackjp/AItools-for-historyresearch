$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..\..")
$PidFile = Join-Path $Root ".runtime\backend.pid"

if (-not (Test-Path $PidFile)) {
    Write-Host "No backend service record was found."
    exit 0
}

$PidValue = Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $PidValue) {
    Remove-Item $PidFile -Force
    Write-Host "Empty runtime record cleaned."
    exit 0
}

$Process = Get-Process -Id ([int]$PidValue) -ErrorAction SilentlyContinue
if ($Process) {
    Stop-Process -Id $Process.Id -Force
    Write-Host "Stopped backend service: PID $PidValue"
} else {
    Write-Host "Backend service is not running. Runtime record cleaned."
}

Remove-Item $PidFile -Force
