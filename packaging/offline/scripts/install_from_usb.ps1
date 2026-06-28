param(
    [string]$BundleDir = (Resolve-Path ".").Path,
    [int]$HealthTimeoutSec = 180,
    [int]$WhisperApiPort = 18080,
    [int]$OllamaPort = 11434,
    [switch]$ForceCpu
)

$ErrorActionPreference = "Stop"

# Resolve the real Docker executable. Calling the bare word "docker" can fail on
# some machines (e.g. broken PATHEXT) where PowerShell resolves the extension-less
# "...\resources\bin\docker" file and refuses to run it in the middle of a pipeline.
$dockerCmd = Get-Command docker.exe -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
}
if (-not $dockerCmd) {
    throw "Docker CLI not found on PATH. Install Docker Desktop and re-run."
}
$docker = $dockerCmd.Source

function Format-Bytes {
    param([long]$Bytes)
    if ($Bytes -ge 1TB) { return "{0:N2} TB" -f ($Bytes / 1TB) }
    if ($Bytes -ge 1GB) { return "{0:N2} GB" -f ($Bytes / 1GB) }
    if ($Bytes -ge 1MB) { return "{0:N2} MB" -f ($Bytes / 1MB) }
    if ($Bytes -ge 1KB) { return "{0:N2} KB" -f ($Bytes / 1KB) }
    return "$Bytes B"
}

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

function Test-HttpHealth {
    param([string]$Url, [int]$TimeoutSec)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200) { return $true }
        } catch {
            Start-Sleep -Seconds 3
        }
    }
    return $false
}

function Stop-Compose {
    param([string]$ComposeFile)
    if (-not (Test-Path $ComposeFile)) { return }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $docker compose -f $ComposeFile down --remove-orphans 2>&1 | Out-Null
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Test-DockerImage {
    param([string]$ImageRef)
    & $docker image inspect $ImageRef 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

function Import-ImageTar {
    param(
        [string]$TarPath,
        [string]$ImageRef,
        [int]$Index = 0,
        [int]$Total = 0
    )
    $prefix = if ($Total -gt 0) { "[import] ($Index/$Total)" } else { "[import]" }
    if (Test-Path $TarPath) {
        $tarName = Split-Path $TarPath -Leaf
        $tarSize = (Get-Item $TarPath).Length
        Write-Host "$prefix Loading $ImageRef" -ForegroundColor Cyan
        Write-Host "$prefix   source : $tarName ($(Format-Bytes $tarSize))"
        $started = Get-Date
        & $docker load -i $TarPath
        if ($LASTEXITCODE -ne 0) {
            throw "docker load failed for $ImageRef from $TarPath (exit code $LASTEXITCODE)."
        }
        $elapsed = (Get-Date) - $started
        Write-Host "$prefix   done   : $ImageRef loaded in $($elapsed.ToString('mm\:ss'))" -ForegroundColor Green
    } elseif (Test-DockerImage -ImageRef $ImageRef) {
        Write-Host "$prefix $ImageRef tar not found; using existing Docker image." -ForegroundColor Yellow
    } else {
        throw "Image $ImageRef not found at $TarPath and not loaded in Docker. Re-run build_usb_bundle.ps1."
    }
}

function Test-GpuCapability {
    param([string]$GpuImageRef)
    if (-not (Test-DockerImage -ImageRef $GpuImageRef)) { return $false }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $docker run --rm --gpus all --entrypoint nvidia-smi $GpuImageRef 2>&1 | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $prev
    }
}

$bundleDir = (Resolve-Path $BundleDir).Path
$envPath = Join-Path $bundleDir ".env.bundle"
$imagesDir = Join-Path $bundleDir "images"
$gpuTar = Join-Path $imagesDir "meeting-assistant-gpu-bundle.tar"
$cpuTar = Join-Path $imagesDir "meeting-assistant-cpu-bundle.tar"
$ollamaTar = Join-Path $imagesDir "meeting-assistant-ollama-bundle.tar"
$gpuImageRef = "meeting-assistant:gpu-bundle"
$cpuImageRef = "meeting-assistant:cpu-bundle"
$ollamaImageRef = "meeting-assistant:ollama-bundle"
$baseCompose = Join-Path $bundleDir "compose\compose.yml"
$gpuCompose = Join-Path $bundleDir "compose\compose.gpu.yml"

if (-not (Test-Path $envPath)) {
    throw ".env.bundle not found in $bundleDir"
}
if (-not (Test-Path $baseCompose)) {
    throw "compose.yml not found at $baseCompose"
}

Write-Host "[import] Using Docker CLI: $docker"

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

# --- Load all images (GPU + CPU Whisper, Ollama) ---
$imageJobs = @(
    @{ Tar = $cpuTar; Ref = $cpuImageRef },
    @{ Tar = $gpuTar; Ref = $gpuImageRef },
    @{ Tar = $ollamaTar; Ref = $ollamaImageRef }
)
$totalImages = $imageJobs.Count
$presentTars = $imageJobs | Where-Object { Test-Path $_.Tar }
$totalTarBytes = ($presentTars | ForEach-Object { (Get-Item $_.Tar).Length } | Measure-Object -Sum).Sum
if (-not $totalTarBytes) { $totalTarBytes = 0 }

Write-Host ""
Write-Host "=== Importing Docker images ($totalImages images, $(Format-Bytes $totalTarBytes) of tarballs) ===" -ForegroundColor Cyan
$importStarted = Get-Date
$index = 0
foreach ($job in $imageJobs) {
    $index++
    Import-ImageTar -TarPath $job.Tar -ImageRef $job.Ref -Index $index -Total $totalImages
}
$importElapsed = (Get-Date) - $importStarted
Write-Host "[import] All images processed in $($importElapsed.ToString('mm\:ss'))." -ForegroundColor Green
Write-Host ""

$whisperPort = if ($env:WHISPER_API_PORT) { [int]$env:WHISPER_API_PORT } else { $WhisperApiPort }
$ollamaPort = if ($env:OLLAMA_PORT) { [int]$env:OLLAMA_PORT } else { $OllamaPort }
$whisperHealth = "http://127.0.0.1:$whisperPort/health"
$ollamaHealth = "http://127.0.0.1:$ollamaPort/api/tags"

# Clean any prior stack.
Stop-Compose -ComposeFile $baseCompose

$activeProfile = ""

# --- Try GPU first (best-effort) unless forced to CPU ---
$gpuCapable = $false
if (-not $ForceCpu) {
    Write-Host "[import] Probing GPU capability (docker run --gpus all ... nvidia-smi)..."
    $gpuCapable = Test-GpuCapability -GpuImageRef $gpuImageRef
    if ($gpuCapable) {
        Write-Host "[import] GPU available. Starting GPU profile..."
        & $docker compose --env-file $envPath -f $baseCompose -f $gpuCompose up -d
        $whisperOk = Test-HttpHealth -Url $whisperHealth -TimeoutSec $HealthTimeoutSec
        $ollamaOk = Test-HttpHealth -Url $ollamaHealth -TimeoutSec $HealthTimeoutSec
        if ($whisperOk -and $ollamaOk) {
            $activeProfile = "gpu"
        } else {
            Write-Warning "[import] GPU profile failed health checks (whisper=$whisperOk ollama=$ollamaOk). Falling back to CPU."
            Stop-Compose -ComposeFile $baseCompose
        }
    } else {
        Write-Host "[import] GPU not available (no NVIDIA Container Toolkit / driver). Using CPU profile."
    }
}

# --- CPU fallback / default ---
if (-not $activeProfile) {
    Write-Host "[import] Starting CPU profile..."
    & $docker compose --env-file $envPath -f $baseCompose up -d
    $whisperOk = Test-HttpHealth -Url $whisperHealth -TimeoutSec $HealthTimeoutSec
    $ollamaOk = Test-HttpHealth -Url $ollamaHealth -TimeoutSec $HealthTimeoutSec
    if (-not $whisperOk) {
        throw "Whisper inference failed health check on $whisperHealth"
    }
    if (-not $ollamaOk) {
        throw "Ollama failed health check on $ollamaHealth"
    }
    $activeProfile = "cpu"
}

$profilePath = Join-Path $bundleDir ".active_profile"
Set-Content -Path $profilePath -Value $activeProfile -Encoding ASCII
Write-Host "[import] Active inference profile: $activeProfile"
Write-Host "[import] Whisper API: $whisperHealth"
Write-Host "[import] Ollama API: $ollamaHealth"
Write-Host "[import] SQLite data dir: $($env:MEETING_ASSISTANT_DATA_DIR)"
Write-Host "[import] Meeting outputs: $($env:MEETING_ASSISTANT_OUTPUT_ROOT)"
Write-Host "[import] Run launch_host_client.ps1 to open the desktop app."
