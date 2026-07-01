param(
    [string]$OutputDir = ".\packaging\offline\usb-bundle",
    [string]$GpuImageTag = "meeting-assistant:gpu-bundle",
    [string]$CpuImageTag = "meeting-assistant:cpu-bundle",
    [string]$OllamaImageTag = "meeting-assistant:ollama-bundle",
    [string]$WhisperModel = "large-v3-turbo",
    [string]$WhisperAlignLanguage = "ar",
    [string]$OllamaBaseModel = "gemma4:e4b",
    [string]$OllamaModel = "gemma4:e4b128k",
    [int]$OllamaNumCtx = 131072,
    [switch]$SkipHostClient
)

$ErrorActionPreference = "Stop"

# BuildKit is required for the cache mounts and # syntax= directives in the Dockerfiles.
$env:DOCKER_BUILDKIT = "1"

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

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
Set-Location $RepoRoot

$TotalSteps = if ($SkipHostClient) { 6 } else { 7 }
$Step = 0
$BuildStarted = Get-Date

function Write-Step {
    param([string]$Message)
    $script:Step++
    Write-Host ""
    Write-Host "=== [$Step/$TotalSteps] $Message ===" -ForegroundColor Cyan
}

function Write-Info {
    param([string]$Message)
    Write-Host "[export] $Message"
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[export] $Message" -ForegroundColor Green
}

function Format-Bytes {
    param([long]$Bytes)
    if ($Bytes -ge 1TB) { return "{0:N2} TB" -f ($Bytes / 1TB) }
    if ($Bytes -ge 1GB) { return "{0:N2} GB" -f ($Bytes / 1GB) }
    if ($Bytes -ge 1MB) { return "{0:N2} MB" -f ($Bytes / 1MB) }
    if ($Bytes -ge 1KB) { return "{0:N2} KB" -f ($Bytes / 1KB) }
    return "$Bytes B"
}

function Get-DockerImageBytes {
    param([string]$ImageRef)
    $raw = & $docker image inspect $ImageRef --format "{{.Size}}" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $raw) { return $null }
    return [long]$raw
}

function Get-WhisperDockerBuildArgs {
    $args = @(
        "--build-arg", "PRELOAD_MODELS=1",
        "--build-arg", "WHISPER_MODEL=$WhisperModel",
        "--build-arg", "WHISPER_ALIGN_LANGUAGE=$WhisperAlignLanguage"
    )
    $token = $env:HF_TOKEN
    if (-not $token) { $token = $env:HF_ACCESS_TOKEN }
    if (-not $token) { $token = $env:HUGGING_FACE_HUB_TOKEN }
    if ($token) {
        Write-Info "HF token found in environment (authenticated Whisper preload)."
        $args += @("--build-arg", "HF_TOKEN=$token")
    } else {
        Write-Warning "No HF_TOKEN in environment. Whisper download may be slow or stall on Hub rate limits."
        Write-Warning "Set HF_TOKEN before building: `$env:HF_TOKEN = 'hf_...'"
    }
    return $args
}

function Invoke-DockerBuild {
    param(
        [string]$Label,
        [string]$Dockerfile,
        [string[]]$BuildArgs,
        [string]$Tag
    )
    $started = Get-Date
    Write-Info "Dockerfile: $Dockerfile"
    Write-Info "Tag: $Tag"
    if ($BuildArgs.Count -gt 0) {
        Write-Info ("Build args: " + ($BuildArgs -join " "))
    }
    Write-Info "Starting build (first run may take 30-90+ min per Whisper image; cached layers are much faster)..."
    Write-Host ""

    $dockerArgs = @(
        "build",
        "--progress=plain",
        "-f", $Dockerfile
    ) + $BuildArgs + @("-t", $Tag, ".")

    & $docker @dockerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Docker build failed for $Label (exit $LASTEXITCODE)"
    }

    $elapsed = (Get-Date) - $started
    $size = Get-DockerImageBytes -ImageRef $Tag
    if ($null -ne $size) {
        $sizeText = Format-Bytes $size
    } else {
        $sizeText = "unknown"
    }
    Write-Ok "$Label built in $($elapsed.ToString('hh\:mm\:ss')) (image size: $sizeText)"
}

function Invoke-DockerSave {
    param(
        [string]$Label,
        [string]$ImageRef,
        [string]$TarPath
    )
    $started = Get-Date
    Write-Info "Saving $Label to $(Split-Path $TarPath -Leaf)"
    & $docker save -o $TarPath $ImageRef
    if ($LASTEXITCODE -ne 0) {
        throw "docker save failed for $Label (exit $LASTEXITCODE)"
    }
    $elapsed = (Get-Date) - $started
    $fileSize = (Get-Item $TarPath).Length
    Write-Ok "$Label tar saved in $($elapsed.ToString('mm\:ss')) ($(Format-Bytes $fileSize))"
}

function Assert-PunktBaked {
    <#
    Fail the build early if the NLTK sentence tokenizers were not baked into a Whisper
    image. Missing punkt_tab is the exact cause of the offline whisperx.align() HTTP 500,
    so we verify it here rather than discovering it on the air-gapped target.
    #>
    param(
        [string]$Label,
        [string]$ImageRef
    )
    Write-Info "Verifying NLTK punkt_tab is baked into $Label ($ImageRef)..."
    $py = 'import nltk; nltk.data.find("tokenizers/punkt_tab/english"); nltk.data.find("tokenizers/punkt"); print("PUNKT_BAKED_OK")'
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & $docker run --rm --entrypoint python $ImageRef -c $py 2>&1
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    $text = ($out | Out-String).Trim()
    if ($code -ne 0 -or $text -notmatch "PUNKT_BAKED_OK") {
        throw "NLTK punkt_tab/punkt not baked into $Label. whisperx.align() would 500 offline. Output: $text"
    }
    Write-Ok "$Label has NLTK tokenizers baked (punkt_tab + punkt)."
}

# --- Banner ---
Write-Host ""
Write-Host "Meeting Assistant - offline USB bundle build" -ForegroundColor Cyan
Write-Host "Repo:   $RepoRoot"
Write-Host "Output: $OutputDir"
Write-Host ""
Write-Info "Whisper model: $WhisperModel (align: $WhisperAlignLanguage)"
Write-Info "Ollama: $OllamaBaseModel then $OllamaModel (num_ctx=$OllamaNumCtx)"
if ($SkipHostClient) {
    Write-Info "Host client: skipped (-SkipHostClient)"
} else {
    Write-Info "Host client: MeetingAssistant.exe via PyInstaller"
}
Write-Host ""

# --- Pre-flight ---
Write-Step "Pre-flight checks"
try {
    $dockerVersion = & $docker version --format "{{.Server.Version}}" 2>$null
    if (-not $dockerVersion) { throw "docker version returned no server version" }
    Write-Ok "Docker server: $dockerVersion (BuildKit enabled)"
} catch {
    throw "Docker is not available. Start Docker Desktop and retry. $_"
}

$resolvedOutput = Resolve-Path $OutputDir -ErrorAction SilentlyContinue
if (-not $resolvedOutput) {
    $resolvedOutput = (New-Item -ItemType Directory -Path $OutputDir -Force).FullName
}
$drive = (Get-Item $resolvedOutput).PSDrive
if ($drive) {
    $freeGb = [math]::Round($drive.Free / 1GB, 1)
    Write-Info "Free disk on $($drive.Name): ${freeGb} GB (recommend 80+ GB for first build)"
    if ($freeGb -lt 40) {
        Write-Warning "Low disk space - the bundle may fail during docker build or save."
    }
}

if (-not $SkipHostClient) {
    # Prefer py.exe explicitly; the bare "py" can be shadowed or unresolved on some PATHs.
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $py) {
        Write-Warning "Python launcher 'py.exe' not found - host client build may fail. Install Python 3.12."
    } else {
        Write-Ok "Python launcher found: $($py.Source)"
    }
}

# --- Prepare output tree ---
Write-Step "Prepare bundle directories"
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$imagesDir = Join-Path $OutputDir "images"
$composeDir = Join-Path $OutputDir "compose"
$binDir = Join-Path $OutputDir "bin"
$dataDir = Join-Path $OutputDir "data"
$outputsDir = Join-Path $OutputDir "meeting_outputs"
New-Item -ItemType Directory -Path $imagesDir, $composeDir, $binDir, $dataDir, $outputsDir -Force | Out-Null
Write-Ok "Bundle tree ready under $(Resolve-Path $OutputDir)"

# --- Docker images ---
Write-Step "Build GPU Whisper inference image (models baked in)"
Invoke-DockerBuild -Label "GPU Whisper inference" `
    -Dockerfile "packaging/offline/images/Dockerfile.gpu" `
    -BuildArgs (Get-WhisperDockerBuildArgs) `
    -Tag $GpuImageTag

Write-Step "Build CPU Whisper inference image (models baked in)"
Invoke-DockerBuild -Label "CPU Whisper inference" `
    -Dockerfile "packaging/offline/images/Dockerfile.cpu" `
    -BuildArgs (Get-WhisperDockerBuildArgs) `
    -Tag $CpuImageTag

# Fail fast if the tokenizers were dropped from a future preload/Dockerfile edit.
Assert-PunktBaked -Label "GPU Whisper inference" -ImageRef $GpuImageTag
Assert-PunktBaked -Label "CPU Whisper inference" -ImageRef $CpuImageTag

Write-Step "Build Ollama image (base then derived model)"
Invoke-DockerBuild -Label "Ollama summarization" `
    -Dockerfile "packaging/offline/images/Dockerfile.ollama" `
    -BuildArgs @(
        "--build-arg", "OLLAMA_BASE_MODEL=$OllamaBaseModel",
        "--build-arg", "OLLAMA_MODEL=$OllamaModel",
        "--build-arg", "OLLAMA_NUM_CTX=$OllamaNumCtx"
    ) `
    -Tag $OllamaImageTag

$gpuTar = Join-Path $imagesDir "meeting-assistant-gpu-bundle.tar"
$cpuTar = Join-Path $imagesDir "meeting-assistant-cpu-bundle.tar"
$ollamaTar = Join-Path $imagesDir "meeting-assistant-ollama-bundle.tar"

Write-Step "Export Docker images to tar files"
Invoke-DockerSave -Label "GPU Whisper" -ImageRef $GpuImageTag -TarPath $gpuTar
Invoke-DockerSave -Label "CPU Whisper" -ImageRef $CpuImageTag -TarPath $cpuTar
Invoke-DockerSave -Label "Ollama" -ImageRef $OllamaImageTag -TarPath $ollamaTar

Write-Step "Copy compose files, scripts, and RUNBOOK"
Copy-Item (Join-Path $RepoRoot "packaging\offline\compose\compose.yml") (Join-Path $composeDir "compose.yml") -Force
Copy-Item (Join-Path $RepoRoot "packaging\offline\compose\compose.gpu.yml") (Join-Path $composeDir "compose.gpu.yml") -Force
Copy-Item (Join-Path $RepoRoot "packaging\offline\scripts\install_from_usb.ps1") (Join-Path $OutputDir "install_from_usb.ps1") -Force
Copy-Item (Join-Path $RepoRoot "packaging\offline\scripts\launch_host_client.ps1") (Join-Path $OutputDir "launch_host_client.ps1") -Force
Copy-Item (Join-Path $RepoRoot "packaging\offline\scripts\accept_offline_bundle.ps1") (Join-Path $OutputDir "accept_offline_bundle.ps1") -Force
$acceptScriptPath = Join-Path $OutputDir "accept_offline_bundle.ps1"
$acceptScriptText = Get-Content -Path $acceptScriptPath -Raw
if ($acceptScriptText -notmatch "function Invoke-NativeCommand") {
    throw "accept_offline_bundle.ps1 is missing Invoke-NativeCommand (offline curl probe would abort on stderr)."
}
if ($acceptScriptText -notmatch "Invoke-NativeCommand.*huggingface\.co") {
    throw "accept_offline_bundle.ps1 must probe huggingface.co via Invoke-NativeCommand."
}
Copy-Item (Join-Path $RepoRoot "packaging\offline\scripts\clean_install.ps1") (Join-Path $OutputDir "clean_install.ps1") -Force
Copy-Item (Join-Path $RepoRoot "packaging\offline\RUNBOOK.txt") (Join-Path $OutputDir "RUNBOOK.txt") -Force
Write-Ok "Operator scripts and compose files copied"

$bundleRootEscaped = (Resolve-Path $OutputDir).Path
$envContent = @"
MEETING_ASSISTANT_OFFLINE_BUNDLE=1
MEETING_ASSISTANT_WHISPER_API_URL=http://127.0.0.1:18080
WHISPER_API_PORT=18080

MEETING_ASSISTANT_OLLAMA_BASE_URL=http://127.0.0.1:11434
MEETING_ASSISTANT_OLLAMA_MODEL=$OllamaModel
OLLAMA_PORT=11434

MEETING_ASSISTANT_WHISPER_MODEL=$WhisperModel
MEETING_ASSISTANT_WHISPER_ALIGN_LANGUAGE=$WhisperAlignLanguage
MEETING_ASSISTANT_SPEAKER_DIARIZATION=0

MEETING_ASSISTANT_DATA_DIR=$bundleRootEscaped\data
MEETING_ASSISTANT_OUTPUT_ROOT=$bundleRootEscaped\meeting_outputs
"@

$envBundlePath = Join-Path $OutputDir ".env.bundle"
Set-Content -Path $envBundlePath -Value $envContent -Encoding UTF8
Write-Ok ".env.bundle written (Ollama model: $OllamaModel)"

if (-not $SkipHostClient) {
    Write-Step "Build PyInstaller host client (MeetingAssistant.exe)"
    & (Join-Path $RepoRoot "packaging\offline\host-client\build_host_client.ps1") -DistDir $binDir
}

# --- Summary ---
$totalElapsed = (Get-Date) - $BuildStarted
Write-Host ""
Write-Host "=== Build complete ===" -ForegroundColor Green
Write-Host "Bundle path: $(Resolve-Path $OutputDir)"
Write-Host "Total time:  $($totalElapsed.ToString('hh\:mm\:ss'))"
Write-Host ""
Write-Host "Artifacts:" -ForegroundColor Cyan
$artifactRows = @(
    @{ Name = "GPU Whisper tar"; Path = $gpuTar },
    @{ Name = "CPU Whisper tar"; Path = $cpuTar },
    @{ Name = "Ollama tar"; Path = $ollamaTar },
    @{ Name = "Host client"; Path = (Join-Path $binDir "MeetingAssistant.exe") }
)
$bundleBytes = 0L
foreach ($row in $artifactRows) {
    if (Test-Path $row.Path) {
        $len = (Get-Item $row.Path).Length
        $bundleBytes += $len
        $label = $row.Name
        $size = Format-Bytes $len
        Write-Host ("  {0,-18} {1}" -f $label, $size)
    } else {
        $label = $row.Name
        Write-Host ("  {0,-18} (missing)" -f $label) -ForegroundColor Yellow
    }
}
$totalLabel = "Bundle total"
$totalSize = Format-Bytes $bundleBytes
Write-Host ("  {0,-18} {1}" -f $totalLabel, $totalSize)
Write-Host ""
Write-Info "Next: copy the entire folder to USB."
Write-Info "On target: install_from_usb.ps1, then accept_offline_bundle.ps1, then launch_host_client.ps1"
Write-Info "Operator guide: RUNBOOK.txt"
