param(
    [string]$OutputDir = ".\packaging\offline\usb-bundle",
    [string]$GpuImageTag = "meeting-assistant:gpu-bundle",
    [string]$CpuImageTag = "meeting-assistant:cpu-bundle",
    [switch]$SkipHostClient
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
Set-Location $RepoRoot

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$imagesDir = Join-Path $OutputDir "images"
$composeDir = Join-Path $OutputDir "compose"
$binDir = Join-Path $OutputDir "bin"
$dataDir = Join-Path $OutputDir "data"
$outputsDir = Join-Path $OutputDir "meeting_outputs"
New-Item -ItemType Directory -Path $imagesDir, $composeDir, $binDir, $dataDir, $outputsDir -Force | Out-Null

Write-Host "[export] Building GPU inference image (models baked in)..."
docker build `
    -f packaging/offline/images/Dockerfile.gpu `
    --build-arg PRELOAD_MODELS=1 `
    --build-arg WHISPER_MODEL=large-v3-turbo `
    --build-arg WHISPER_ALIGN_LANGUAGE=ar `
    -t $GpuImageTag `
    .

Write-Host "[export] Building CPU inference image (models baked in)..."
docker build `
    -f packaging/offline/images/Dockerfile.cpu `
    --build-arg PRELOAD_MODELS=1 `
    --build-arg WHISPER_MODEL=large-v3-turbo `
    --build-arg WHISPER_ALIGN_LANGUAGE=ar `
    -t $CpuImageTag `
    .

$gpuTar = Join-Path $imagesDir "meeting-assistant-gpu-bundle.tar"
$cpuTar = Join-Path $imagesDir "meeting-assistant-cpu-bundle.tar"

Write-Host "[export] Saving images..."
docker save -o $gpuTar $GpuImageTag
docker save -o $cpuTar $CpuImageTag

Copy-Item (Join-Path $RepoRoot "packaging\offline\compose\compose.gpu.yml") (Join-Path $composeDir "compose.gpu.yml") -Force
Copy-Item (Join-Path $RepoRoot "packaging\offline\compose\compose.cpu.yml") (Join-Path $composeDir "compose.cpu.yml") -Force
Copy-Item (Join-Path $RepoRoot "packaging\offline\scripts\install_from_usb.ps1") (Join-Path $OutputDir "install_from_usb.ps1") -Force
Copy-Item (Join-Path $RepoRoot "packaging\offline\scripts\launch_host_client.ps1") (Join-Path $OutputDir "launch_host_client.ps1") -Force
Copy-Item (Join-Path $RepoRoot "packaging\offline\scripts\accept_offline_bundle.ps1") (Join-Path $OutputDir "accept_offline_bundle.ps1") -Force
Copy-Item (Join-Path $RepoRoot "packaging\offline\README.md") (Join-Path $OutputDir "RUNBOOK.txt") -Force

$bundleRootEscaped = (Resolve-Path $OutputDir).Path
$envContent = @"
MEETING_ASSISTANT_OFFLINE_BUNDLE=1
MEETING_ASSISTANT_WHISPER_API_URL=http://127.0.0.1:18080
WHISPER_API_PORT=18080

MEETING_ASSISTANT_OLLAMA_BASE_URL=http://127.0.0.1:11434
MEETING_ASSISTANT_OLLAMA_MODEL=gemma4:e4b128k

MEETING_ASSISTANT_WHISPER_MODEL=large-v3-turbo
MEETING_ASSISTANT_WHISPER_ALIGN_LANGUAGE=ar
MEETING_ASSISTANT_SPEAKER_DIARIZATION=0

MEETING_ASSISTANT_DATA_DIR=$bundleRootEscaped\data
MEETING_ASSISTANT_OUTPUT_ROOT=$bundleRootEscaped\meeting_outputs
"@

Set-Content -Path (Join-Path $OutputDir ".env.bundle") -Value $envContent -Encoding UTF8

if (-not $SkipHostClient) {
    Write-Host "[export] Building PyInstaller host client..."
    & (Join-Path $RepoRoot "packaging\offline\host-client\build_host_client.ps1") -DistDir $binDir
}

Write-Host "[export] Offline USB bundle ready at: $OutputDir"
Write-Host "[export] Copy the entire folder to USB. On target: install_from_usb.ps1 -> accept_offline_bundle.ps1 -> launch_host_client.ps1"
Write-Host "[export] Operator guide: RUNBOOK.txt"
