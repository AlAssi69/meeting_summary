param(
    [string]$BundleDir = (Resolve-Path ".").Path,
    [int]$HealthTimeoutSec = 180,
    [int]$WhisperApiPort = 18080
)

$ErrorActionPreference = "Stop"

function Import-DotEnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return @{} }
    $vars = @{}
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $key = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()
        $vars[$key] = $value
        Set-Item -Path "env:$key" -Value $value
    }
    return $vars
}

function Test-WhisperHealth {
    param([int]$Port, [int]$TimeoutSec)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $url = "http://127.0.0.1:$Port/health"
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200) { return $true }
        } catch {
            Start-Sleep -Seconds 3
        }
    }
    return $false
}

function Stop-WhisperCompose {
    param([string]$ComposeFile)
    if (-not (Test-Path $ComposeFile)) { return }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        docker compose -f $ComposeFile down --remove-orphans 2>&1 | Out-Null
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Test-DockerImage {
    param([string]$ImageRef)
    docker image inspect $ImageRef 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

$bundleDir = (Resolve-Path $BundleDir).Path
$envPath = Join-Path $bundleDir ".env.bundle"
$cpuTar = Join-Path $bundleDir "images\meeting-assistant-cpu-bundle.tar"
$cpuImageRef = "meeting-assistant:cpu-bundle"
$gpuCompose = Join-Path $bundleDir "compose\compose.gpu.yml"
$cpuCompose = Join-Path $bundleDir "compose\compose.cpu.yml"

if (-not (Test-Path $envPath)) {
    throw ".env.bundle not found in $bundleDir"
}

Import-DotEnvFile -Path $envPath | Out-Null

if (-not $env:MEETING_ASSISTANT_DATA_DIR) {
    $env:MEETING_ASSISTANT_DATA_DIR = Join-Path $bundleDir "data"
}
if (-not $env:MEETING_ASSISTANT_OUTPUT_ROOT) {
    $env:MEETING_ASSISTANT_OUTPUT_ROOT = Join-Path $bundleDir "meeting_outputs"
}

New-Item -ItemType Directory -Path $env:MEETING_ASSISTANT_DATA_DIR, $env:MEETING_ASSISTANT_OUTPUT_ROOT -Force | Out-Null

# Persist resolved paths back into .env.bundle for launch scripts.
$envContent = Get-Content $envPath -Raw
if ($envContent -notmatch "MEETING_ASSISTANT_DATA_DIR=") {
    Add-Content $envPath "MEETING_ASSISTANT_DATA_DIR=$($env:MEETING_ASSISTANT_DATA_DIR)"
}
if ($envContent -notmatch "MEETING_ASSISTANT_OUTPUT_ROOT=") {
    Add-Content $envPath "MEETING_ASSISTANT_OUTPUT_ROOT=$($env:MEETING_ASSISTANT_OUTPUT_ROOT)"
}

Write-Host "[import] Loading CPU container image..."
if (Test-Path $cpuTar) {
    docker load -i $cpuTar
} elseif (Test-DockerImage -ImageRef $cpuImageRef) {
    Write-Host "[import] CPU bundle tar not found; using existing Docker image $cpuImageRef"
} else {
    throw @"
CPU bundle not found at $cpuTar and Docker image $cpuImageRef is not loaded.
Build the bundle first, for example:
  .\packaging\offline\scripts\build_usb_bundle.ps1
Or load the image on this machine:
  docker load -i images\meeting-assistant-cpu-bundle.tar
"@
}

$port = if ($env:WHISPER_API_PORT) { [int]$env:WHISPER_API_PORT } else { $WhisperApiPort }

Stop-WhisperCompose -ComposeFile $gpuCompose
Stop-WhisperCompose -ComposeFile $cpuCompose

Write-Host "[import] Starting CPU inference profile..."
docker compose --env-file $envPath -f $cpuCompose up -d
if (-not (Test-WhisperHealth -Port $port -TimeoutSec $HealthTimeoutSec)) {
    throw "CPU inference profile failed health check on http://127.0.0.1:$port/health"
}
Write-Host "[import] CPU profile healthy on port $port"

$profilePath = Join-Path $bundleDir ".active_profile"
Set-Content -Path $profilePath -Value "cpu" -Encoding ASCII
Write-Host "[import] Active inference profile: cpu"
Write-Host "[import] SQLite data dir: $($env:MEETING_ASSISTANT_DATA_DIR)"
Write-Host "[import] Meeting outputs: $($env:MEETING_ASSISTANT_OUTPUT_ROOT)"
Write-Host "[import] Run launch_host_client.ps1 to open the desktop app."
