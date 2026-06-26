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
    if (Test-Path $ComposeFile) {
        docker compose -f $ComposeFile down --remove-orphans 2>$null | Out-Null
    }
}

$bundleDir = (Resolve-Path $BundleDir).Path
$envPath = Join-Path $bundleDir ".env.bundle"
$gpuTar = Join-Path $bundleDir "images\meeting-assistant-gpu-bundle.tar"
$cpuTar = Join-Path $bundleDir "images\meeting-assistant-cpu-bundle.tar"
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

Write-Host "[import] Loading container images..."
if (Test-Path $gpuTar) { docker load -i $gpuTar }
if (Test-Path $cpuTar) { docker load -i $cpuTar }

$activeProfile = "cpu"
$port = if ($env:WHISPER_API_PORT) { [int]$env:WHISPER_API_PORT } else { $WhisperApiPort }

Stop-WhisperCompose -ComposeFile $gpuCompose
Stop-WhisperCompose -ComposeFile $cpuCompose

Write-Host "[import] Attempting GPU inference profile (may fail on Hyper-V without GPU passthrough)..."
try {
    docker compose --env-file $envPath -f $gpuCompose up -d
    if (Test-WhisperHealth -Port $port -TimeoutSec $HealthTimeoutSec) {
        $activeProfile = "gpu"
        Write-Host "[import] GPU profile healthy on port $port"
    } else {
        Write-Host "[import] GPU profile did not become healthy; falling back to CPU..."
        Stop-WhisperCompose -ComposeFile $gpuCompose
    }
} catch {
    Write-Host "[import] GPU profile failed to start: $_"
    Stop-WhisperCompose -ComposeFile $gpuCompose
}

if ($activeProfile -ne "gpu") {
    Write-Host "[import] Starting CPU inference profile..."
    docker compose --env-file $envPath -f $cpuCompose up -d
    if (-not (Test-WhisperHealth -Port $port -TimeoutSec $HealthTimeoutSec)) {
        throw "CPU inference profile failed health check on http://127.0.0.1:$port/health"
    }
    Write-Host "[import] CPU profile healthy on port $port"
}

$profilePath = Join-Path $bundleDir ".active_profile"
Set-Content -Path $profilePath -Value $activeProfile -Encoding ASCII
Write-Host "[import] Active inference profile: $activeProfile"
Write-Host "[import] SQLite data dir: $($env:MEETING_ASSISTANT_DATA_DIR)"
Write-Host "[import] Meeting outputs: $($env:MEETING_ASSISTANT_OUTPUT_ROOT)"
Write-Host "[import] Run launch_host_client.ps1 to open the desktop app."
