param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path,
    [string]$VenvDir = "",
    [string]$DistDir = (Join-Path $PSScriptRoot "dist")
)

$ErrorActionPreference = "Stop"

if (-not $VenvDir) {
    $VenvDir = Join-Path $RepoRoot ".venv-host-client"
}

$python = Join-Path $VenvDir "Scripts\python.exe"
$pip = Join-Path $VenvDir "Scripts\pip.exe"

if (-not (Test-Path $python)) {
    Write-Host "[host-client] Creating venv at $VenvDir"
    # Resolve py.exe explicitly; the bare "py" can be shadowed or unresolved on locked-down PATHs.
    $pyCmd = Get-Command py.exe -ErrorAction SilentlyContinue
    if (-not $pyCmd) { $pyCmd = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $pyCmd) {
        throw "Python launcher 'py.exe' not found on PATH. Install Python 3.12 (with the py launcher) and re-run."
    }
    & $pyCmd.Source -3.12 -m venv $VenvDir
}

Write-Host "[host-client] Installing host dependencies..."
& $pip install --upgrade pip wheel setuptools
& $pip install -r (Join-Path $PSScriptRoot "requirements-host.txt")
& $pip install pyinstaller>=6.0

New-Item -ItemType Directory -Path $DistDir -Force | Out-Null

Write-Host "[host-client] Building MeetingAssistant.exe..."
Push-Location $RepoRoot
try {
    & $python -m PyInstaller `
        --noconfirm `
        --distpath $DistDir `
        --workpath (Join-Path $PSScriptRoot "build") `
        (Join-Path $PSScriptRoot "meeting_assistant.spec")
} finally {
    Pop-Location
}

$exe = Join-Path $DistDir "MeetingAssistant.exe"
if (-not (Test-Path $exe)) {
    throw "Build failed: $exe not found"
}

Write-Host "[host-client] Built: $exe"
