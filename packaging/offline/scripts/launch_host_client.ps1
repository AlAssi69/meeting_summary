param(
    [string]$BundleDir = (Resolve-Path ".").Path
)

$ErrorActionPreference = "Stop"

$bundleDir = (Resolve-Path $BundleDir).Path
$envPath = Join-Path $bundleDir ".env.bundle"
$exe = Join-Path $bundleDir "bin\MeetingAssistant.exe"

if (-not (Test-Path $exe)) {
    throw "MeetingAssistant.exe not found at $exe"
}
if (-not (Test-Path $envPath)) {
    throw ".env.bundle not found at $envPath"
}

Get-Content $envPath | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $idx = $line.IndexOf("=")
    if ($idx -lt 1) { return }
    $key = $line.Substring(0, $idx).Trim()
    $value = $line.Substring($idx + 1).Trim()
    Set-Item -Path "env:$key" -Value $value
}

if (-not $env:MEETING_ASSISTANT_DATA_DIR) {
    $env:MEETING_ASSISTANT_DATA_DIR = Join-Path $bundleDir "data"
}
if (-not $env:MEETING_ASSISTANT_OUTPUT_ROOT) {
    $env:MEETING_ASSISTANT_OUTPUT_ROOT = Join-Path $bundleDir "meeting_outputs"
}

New-Item -ItemType Directory -Path $env:MEETING_ASSISTANT_DATA_DIR, $env:MEETING_ASSISTANT_OUTPUT_ROOT -Force | Out-Null

$port = if ($env:WHISPER_API_PORT) { $env:WHISPER_API_PORT } else { "18080" }
$healthUrl = "http://127.0.0.1:$port/health"
try {
    $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5
    if ($resp.StatusCode -ne 200) {
        Write-Warning "Whisper API health check returned HTTP $($resp.StatusCode). Run install_from_usb.ps1 first."
    }
} catch {
    Write-Warning "Whisper API not reachable at $healthUrl. Run install_from_usb.ps1 first."
}

Write-Host "[launch] Starting Meeting Assistant host client..."
Start-Process -FilePath $exe -WorkingDirectory $bundleDir
