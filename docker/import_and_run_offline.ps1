param(
    [string]$BundleDir = ".",
    [ValidateSet("gpu", "cpu")]
    [string]$Profile = "gpu"
)

$ErrorActionPreference = "Stop"

$gpuTar = Join-Path $BundleDir "meeting-assistant-gpu-offline.tar"
$cpuTar = Join-Path $BundleDir "meeting-assistant-cpu-offline.tar"
$composePath = Join-Path $BundleDir "compose.offline.yml"
$envPath = Join-Path $BundleDir ".env.offline"

if (-not (Test-Path $composePath)) {
    throw "compose.offline.yml not found in $BundleDir"
}

if (Test-Path $gpuTar) {
    Write-Host "[import] Loading GPU image tar..."
    docker load -i $gpuTar
}

if (Test-Path $cpuTar) {
    Write-Host "[import] Loading CPU image tar..."
    docker load -i $cpuTar
}

if (-not (Test-Path $envPath)) {
    Write-Host "[import] .env.offline not found; creating with defaults."
    @"
MEETING_ASSISTANT_OLLAMA_BASE_URL=http://host.docker.internal:11434
MEETING_ASSISTANT_OLLAMA_MODEL=gemma4:e4b128k
MEETING_ASSISTANT_WHISPER_MODEL=large-v3
MEETING_ASSISTANT_SPEAKER_DIARIZATION=0
"@ | Set-Content -Path $envPath -Encoding UTF8
}

Write-Host "[import] Starting compose profile: $Profile"
if ($Profile -eq "gpu") {
    docker compose --env-file $envPath -f $composePath up meeting-assistant-gpu
} else {
    docker compose --env-file $envPath -f $composePath up meeting-assistant-cpu
}
