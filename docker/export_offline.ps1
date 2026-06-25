param(
    [string]$OutputDir = ".\docker\offline-bundle",
    [string]$GpuImageTag = "meeting-assistant:gpu-offline",
    [string]$CpuImageTag = "meeting-assistant:cpu-offline",
    [string]$ComposePath = ".\docker\compose.offline.yml"
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

Write-Host "[export] Building GPU image with preloaded models..."
docker build `
  -f docker/Dockerfile.gpu `
  --build-arg PRELOAD_MODELS=1 `
  -t $GpuImageTag `
  .

Write-Host "[export] Building CPU image with preloaded models..."
docker build `
  -f docker/Dockerfile.cpu `
  --build-arg PRELOAD_MODELS=1 `
  -t $CpuImageTag `
  .

$gpuTar = Join-Path $OutputDir "meeting-assistant-gpu-offline.tar"
$cpuTar = Join-Path $OutputDir "meeting-assistant-cpu-offline.tar"

Write-Host "[export] Saving images to tar files..."
docker save -o $gpuTar $GpuImageTag
docker save -o $cpuTar $CpuImageTag

Copy-Item $ComposePath (Join-Path $OutputDir "compose.offline.yml") -Force
Copy-Item ".\docker\import_and_run_offline.ps1" (Join-Path $OutputDir "import_and_run_offline.ps1") -Force

$envTemplate = @"
# Set this to the reachable Ollama endpoint from target laptop.
MEETING_ASSISTANT_OLLAMA_BASE_URL=http://host.docker.internal:11434
MEETING_ASSISTANT_OLLAMA_MODEL=gemma4:e4b128k
MEETING_ASSISTANT_WHISPER_MODEL=large-v3
MEETING_ASSISTANT_SPEAKER_DIARIZATION=0
"@

Set-Content -Path (Join-Path $OutputDir ".env.offline") -Value $envTemplate -Encoding UTF8

Write-Host "[export] Offline bundle ready at: $OutputDir"
Write-Host "[export] Copy this folder to USB and run import_and_run_offline.ps1 on target."
