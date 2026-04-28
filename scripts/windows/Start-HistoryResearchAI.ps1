param(
    [int]$Port = 5000,
    [switch]$SkipInit
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..\..")
$RuntimeDir = Join-Path $Root ".runtime"
$PidFile = Join-Path $RuntimeDir "backend.pid"
$VenvPython = Join-Path $RuntimeDir "venv\Scripts\python.exe"
$AppModule = "app.app"
$Url = "http://127.0.0.1:$Port/"

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

if (-not $SkipInit -and -not (Test-Path $VenvPython)) {
    & (Join-Path $ScriptDir "Initialize-HistoryResearchAI.ps1")
}

if (-not (Test-Path $VenvPython)) {
    throw "Python runtime does not exist. Run Initialize-HistoryResearchAI.ps1 first."
}

if (Test-Path $PidFile) {
    $ExistingPid = Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($ExistingPid) {
        $ExistingProcess = Get-Process -Id ([int]$ExistingPid) -ErrorAction SilentlyContinue
        if ($ExistingProcess) {
            Write-Host "Backend is already running. Opening UI: $Url"
            Start-Process $Url
            exit 0
        }
    }
}

$env:HISTORY_RESEARCH_SERVE_FRONTEND = "1"
$env:FLASK_DEBUG = "0"
$env:PORT = [string]$Port

Write-Host "Starting backend service: $Url"
$Process = Start-Process -FilePath $VenvPython `
    -ArgumentList @("-m", $AppModule) `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path $PidFile -Value $Process.Id -Encoding ASCII

$Ready = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/system/status" -Method Get -TimeoutSec 2 | Out-Null
        $Ready = $true
        break
    } catch {
        if ($Process.HasExited) {
            throw "Backend service failed to start. Exit code: $($Process.ExitCode)"
        }
    }
}

if (-not $Ready) {
    Write-Warning "Backend is still starting. The browser will open now; refresh after a moment if needed."
}

Start-Process $Url
Write-Host "History Research AI started. To stop it, run scripts\windows\Stop-HistoryResearchAI.cmd."
