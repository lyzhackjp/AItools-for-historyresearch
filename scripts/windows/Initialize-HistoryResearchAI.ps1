param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..\..")
$RuntimeDir = Join-Path $Root ".runtime"
$VenvDir = Join-Path $RuntimeDir "venv"
$StampFile = Join-Path $RuntimeDir "install.ok"
$Requirements = Join-Path $Root "requirements.txt"
$FrontendIndex = Join-Path $Root "frontend\dist\index.html"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($ArgumentList -join ' ')"
    }
}

function Test-PythonCandidate {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @()
    )

    & $FilePath @ArgumentList -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 8) and sys.version_info[:2] <= (3, 11) else 1)" 2>$null
    return $LASTEXITCODE -eq 0
}

function Get-PythonCandidate {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        if (Test-PythonCandidate "py" @("-3.11")) {
            return @{ File = "py"; Args = @("-3.11") }
        }
        if (Test-PythonCandidate "py" @("-3")) {
            return @{ File = "py"; Args = @("-3") }
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        if (Test-PythonCandidate "python") {
            return @{ File = "python"; Args = @() }
        }
    }

    throw "Python 3.8-3.11 was not found. Install Python 3.11 and enable Add Python to PATH."
}

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

if ((Test-Path $StampFile) -and -not $Force) {
    Write-Host "Runtime is already initialized."
    exit 0
}

if (-not (Test-Path $Requirements)) {
    throw "requirements.txt was not found: $Requirements"
}

if (-not (Test-Path $FrontendIndex)) {
    Write-Warning "frontend\dist\index.html was not found. Run scripts\windows\Build-WindowsInstaller.ps1 on the build machine first."
}

$Python = Get-PythonCandidate

if (-not (Test-Path (Join-Path $VenvDir "Scripts\python.exe"))) {
    Write-Host "Creating Python virtual environment: $VenvDir"
    Invoke-Checked $Python.File ($Python.Args + @("-m", "venv", $VenvDir))
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
Write-Host "Installing/updating Python dependencies. First run may take a while."
Invoke-Checked $VenvPython @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Checked $VenvPython @("-m", "pip", "install", "-r", $Requirements)

@{
    initialized_at = (Get-Date).ToString("s")
    python = $VenvPython
} | ConvertTo-Json | Set-Content -Path $StampFile -Encoding UTF8

Write-Host "Initialization complete."
