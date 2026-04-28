param(
    [switch]$SkipFrontendBuild,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..\..")
$FrontendDir = Join-Path $Root "frontend"
$InstallerScript = Join-Path $ScriptDir "HistoryResearchAI.iss"
$OutputDir = Join-Path $Root "dist-windows"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [string]$WorkingDirectory = $Root
    )

    Push-Location $WorkingDirectory
    try {
        & $FilePath @ArgumentList
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed: $FilePath $($ArgumentList -join ' ')"
        }
    } finally {
        Pop-Location
    }
}

if (-not $SkipFrontendBuild) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm was not found. Install Node.js 18+ on the build machine first."
    }

    Write-Host "Installing frontend dependencies and building production UI."
    if (Test-Path (Join-Path $FrontendDir "package-lock.json")) {
        Invoke-Checked "npm" @("ci") $FrontendDir
    } else {
        Invoke-Checked "npm" @("install") $FrontendDir
    }
    Invoke-Checked "npm" @("run", "build") $FrontendDir
}

if ($SkipInstaller) {
    Write-Host "Skipped Inno Setup compilation."
    exit 0
}

$IsccCandidates = @(@(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) })

if ($IsccCandidates.Count -eq 0) {
    throw "Inno Setup 6 was not found. Install it, or use -SkipInstaller to only build the frontend."
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
Write-Host "Building Windows installer."
$IsccPath = $IsccCandidates[0]
Invoke-Checked -FilePath $IsccPath -ArgumentList @($InstallerScript) -WorkingDirectory $Root
Write-Host "Installer output directory: $OutputDir"
