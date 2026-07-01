param(
    [string]$BundleDir = (Resolve-Path ".").Path,
    [string]$TestAudioPath = "",
    [switch]$CheckOllama,
    [int]$ApiPort = 0,
    [int]$TimeoutSec = 30
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

function Write-Pass([string]$Message) {
    Write-Host "[PASS] $Message" -ForegroundColor Green
}

function Write-Fail([string]$Message) {
    Write-Host "[FAIL] $Message" -ForegroundColor Red
}

function Invoke-NativeCommand {
    <#
    Run a native executable without letting stderr become a terminating error when
    $ErrorActionPreference is Stop (common with docker/curl 2>&1 merges).
    #>
    param([scriptblock]$Command)
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $Command 2>&1
        return @{
            Output   = $output
            ExitCode = $LASTEXITCODE
        }
    } finally {
        $ErrorActionPreference = $prevEap
    }
}

function Import-DotEnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $key = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()
        Set-Item -Path "env:$key" -Value $value
    }
}

function Get-ActiveContainerName {
    param([string]$Root)
    $name = & $docker ps --filter "name=meeting-assistant-whisper" --format "{{.Names}}" 2>$null
    if ($name) { return ($name | Select-Object -First 1).Trim() }
    return ""
}

$bundleDir = (Resolve-Path $BundleDir).Path
$envPath = Join-Path $bundleDir ".env.bundle"
$failures = 0

Write-Host "[accept] Offline bundle acceptance - $bundleDir"

if (-not (Test-Path $envPath)) {
    Write-Fail ".env.bundle not found at $envPath"
    exit 1
}
Import-DotEnvFile -Path $envPath

if ($ApiPort -le 0) {
    if ($env:WHISPER_API_PORT) {
        $ApiPort = [int]$env:WHISPER_API_PORT
    } else {
        $ApiPort = 18080
    }
}

$baseUrl = if ($env:MEETING_ASSISTANT_WHISPER_API_URL) {
    $env:MEETING_ASSISTANT_WHISPER_API_URL.TrimEnd("/")
} else {
    "http://127.0.0.1:$ApiPort"
}

# --- 1. API connectivity ---
try {
    $health = Invoke-RestMethod -Uri "$baseUrl/health" -TimeoutSec $TimeoutSec
    if ($health.status -eq "ok") {
        Write-Pass "Whisper API health: $baseUrl/health"
    } else {
        Write-Fail "Unexpected health payload: $($health | ConvertTo-Json -Compress)"
        $failures++
    }
} catch {
    Write-Fail "Whisper API health unreachable at $baseUrl/health - $_"
    $failures++
}

# --- 2. Model status ---
$status = $null
try {
    $status = Invoke-RestMethod -Uri "$baseUrl/v1/status" -TimeoutSec $TimeoutSec
    if ($status.model_ready -eq $true) {
        Write-Pass "Model ready (whisper_model=$($status.whisper_model), device=$($status.whisper_device))"
    } else {
        Write-Fail "model_ready is false - baked weights may be missing or cache corrupt"
        $failures++
    }
    if ($status.offline_bundle -eq $true) {
        Write-Pass "offline_bundle flag set in API"
    } else {
        Write-Fail "offline_bundle flag not set in container"
        $failures++
    }
} catch {
    Write-Fail "Whisper API status unreachable at $baseUrl/v1/status - $_"
    $failures++
}

# --- 3. Active profile / CPU fallback awareness ---
$profilePath = Join-Path $bundleDir ".active_profile"
if (Test-Path $profilePath) {
    $activeProfile = (Get-Content $profilePath -Raw).Trim().ToLower()
    Write-Pass "Active compose profile: $activeProfile"
    if ($status -and $activeProfile -eq "cpu" -and $status.whisper_device -ne "cpu") {
        Write-Fail "CPU profile active but API reports whisper_device=$($status.whisper_device)"
        $failures++
    }
    if ($status -and $activeProfile -eq "gpu" -and $status.whisper_device -eq "cpu") {
        Write-Host "[WARN] GPU profile active but runtime is on CPU (driver/reservation fallback inside container)." -ForegroundColor Yellow
    }
} else {
    Write-Fail ".active_profile not found - run install_from_usb.ps1 first"
    $failures++
}

# --- 4. Offline / Hugging Face guards (container env + local-only cache probe) ---
$containerName = Get-ActiveContainerName -Root $bundleDir
if (-not $containerName) {
    Write-Fail "No running inference container (meeting-assistant-whisper)"
    $failures++
} else {
    Write-Pass "Inference container running: $containerName"

    $inspect = & $docker inspect $containerName --format "{{json .Config.Env}}" | ConvertFrom-Json
    $envMap = @{}
    foreach ($entry in $inspect) {
        $eq = $entry.IndexOf("=")
        if ($eq -gt 0) {
            $envMap[$entry.Substring(0, $eq)] = $entry.Substring($eq + 1)
        }
    }

    foreach ($key in @("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")) {
        if ($envMap[$key] -eq "1") {
            Write-Pass "Container env $key=1"
        } else {
            Write-Fail "Container env $key is not 1 (actual: $($envMap[$key]))"
            $failures++
        }
    }

    $offlineProbe = @'
import os
import sys
sys.path.insert(0, '/opt/meeting-assistant/src')
os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
from meeting_assistant.services.whisper_cache_integrity import is_whisper_ct2_cache_complete
ok = is_whisper_ct2_cache_complete()
print('CACHE_OK' if ok else 'CACHE_MISSING')
try:
    from huggingface_hub import hf_hub_download
    hf_hub_download('hf-internal-testing/tiny-random-bert', 'config.json', local_files_only=True)
    print('HF_LOCAL_OK')
except Exception as exc:
    print('HF_LOCAL_FAIL', type(exc).__name__, str(exc)[:120])
# NLTK punkt_tab / punkt are fetched lazily at whisperx.align() time. Missing data is the
# exact cause of the offline HTTP 500 (Resource 'punkt_tab' not found).
try:
    import nltk
    nltk.data.find('tokenizers/punkt_tab/english')
    nltk.data.find('tokenizers/punkt')
    print('PUNKT_OK')
except Exception as exc:
    print('PUNKT_MISSING', type(exc).__name__, str(exc)[:120])
# Load the forced-alignment model offline (baked by preload_models.py --stage align).
try:
    import whisperx
    lang = (os.environ.get('MEETING_ASSISTANT_WHISPER_ALIGN_LANGUAGE') or 'ar').strip().lower()
    whisperx.load_align_model(language_code=lang, device='cpu')
    print('ALIGN_OK')
except Exception as exc:
    print('ALIGN_FAIL', type(exc).__name__, str(exc)[:160])
'@

    $probeResult = Invoke-NativeCommand { $offlineProbe | & $docker exec -i $containerName python3 - }
    $probeText = ($probeResult.Output | Out-String).Trim()
    if ($probeText -match "CACHE_OK") {
        Write-Pass "Whisper CT2 cache complete (local_files_only)"
    } else {
        Write-Fail "Whisper CT2 cache incomplete: $probeText"
        $failures++
    }
    if ($probeText -match "HF_LOCAL_OK") {
        Write-Pass "HF hub local_files_only read succeeded (no network fetch required)"
    } elseif ($probeText -match "HF_LOCAL_FAIL.*LocalEntryNotFound") {
        Write-Pass "HF hub local_files_only blocked missing file without network (expected for probe repo)"
    } else {
        Write-Fail "HF offline probe unexpected: $probeText"
        $failures++
    }
    if ($probeText -match "PUNKT_OK") {
        Write-Pass "NLTK tokenizers baked (punkt_tab + punkt) - alignment will not 500 offline"
    } else {
        Write-Fail "NLTK punkt_tab/punkt missing - whisperx.align() will fail with HTTP 500 offline: $probeText"
        $failures++
    }
    if ($probeText -match "ALIGN_OK") {
        Write-Pass "Forced-alignment model loads offline (language=$($env:MEETING_ASSISTANT_WHISPER_ALIGN_LANGUAGE))"
    } else {
        Write-Fail "Alignment model failed to load offline: $probeText"
        $failures++
    }

    # Outbound Hugging Face connectivity should fail on air-gapped hosts.
    $curlResult = Invoke-NativeCommand { & $docker exec $containerName curl -fsS -m 5 https://huggingface.co }
    if ($curlResult.ExitCode -ne 0) {
        Write-Pass "Outbound HTTPS to huggingface.co blocked or unreachable (offline-safe)"
    } else {
        Write-Host "[WARN] huggingface.co is reachable from the container (online build machine?). Verify air-gap on target." -ForegroundColor Yellow
    }
}

# --- 5. Host data paths ---
$dataDir = if ($env:MEETING_ASSISTANT_DATA_DIR) { $env:MEETING_ASSISTANT_DATA_DIR } else { Join-Path $bundleDir "data" }
$outputRoot = if ($env:MEETING_ASSISTANT_OUTPUT_ROOT) { $env:MEETING_ASSISTANT_OUTPUT_ROOT } else { Join-Path $bundleDir "meeting_outputs" }
foreach ($dir in @($dataDir, $outputRoot)) {
    if (Test-Path $dir) {
        Write-Pass "Persistent host directory exists: $dir"
    } else {
        Write-Fail "Missing persistent host directory: $dir"
        $failures++
    }
}

# --- 6. Optional transcribe smoke test ---
if ($TestAudioPath) {
    $audio = (Resolve-Path $TestAudioPath).Path
    Write-Host "[accept] Transcribe smoke test with $audio"
    try {
        # Use curl.exe explicitly. In PowerShell the bare word "curl" is an alias for
        # Invoke-WebRequest, which cannot perform curl-style multipart uploads (-F) and
        # rejects flags like -X, so it must never be used for this POST. Resolve the real
        # executable (ships with Windows 10 1803+/Windows 11) and fail clearly if absent.
        $curlCmd = Get-Command curl.exe -ErrorAction SilentlyContinue
        if (-not $curlCmd) {
            throw "curl.exe not found on PATH (ships with Windows 10 1803+/Windows 11). Install it or add it to PATH, then re-run."
        }
        $curl = $curlCmd.Source
        $transcribeUrl = "$baseUrl/v1/transcribe"
        $curlResult = Invoke-NativeCommand { & $curl -sS -m 600 -X POST -F "audio=@$audio" $transcribeUrl }
        if ($curlResult.ExitCode -ne 0) {
            throw "curl exited $($curlResult.ExitCode) : $($curlResult.Output)"
        }
        $response = $curlResult.Output | ConvertFrom-Json
        if ($response.text -and ($response.text.ToString().Length -gt 0)) {
            Write-Pass "Transcribe returned $($response.text.ToString().Length) characters"
        } else {
            Write-Fail "Transcribe returned empty text: $($curlResult.Output)"
            $failures++
        }
    } catch {
        Write-Fail "Transcribe smoke test failed - $_"
        $failures++
    }
}

# --- 7. Containerized Ollama (baked model) ---
$ollamaContainer = & $docker ps --filter "name=meeting-assistant-ollama" --format "{{.Names}}" 2>$null
if ($ollamaContainer) {
    Write-Pass "Ollama container running: $(($ollamaContainer | Select-Object -First 1).Trim())"
} else {
    Write-Fail "Ollama container (meeting-assistant-ollama) is not running"
    $failures++
}

$ollamaUrl = if ($env:MEETING_ASSISTANT_OLLAMA_BASE_URL) {
    $env:MEETING_ASSISTANT_OLLAMA_BASE_URL.TrimEnd("/")
} else {
    "http://127.0.0.1:11434"
}
try {
    $tags = Invoke-RestMethod -Uri "$ollamaUrl/api/tags" -TimeoutSec $TimeoutSec
    Write-Pass "Ollama reachable at $ollamaUrl/api/tags"
    $modelName = $env:MEETING_ASSISTANT_OLLAMA_MODEL
    if ($modelName) {
        $names = @()
        if ($tags.models) { $names = $tags.models | ForEach-Object { $_.name } }
        # Accept exact match or the same model without an explicit ":latest" tag.
        $matched = ($names -contains $modelName) -or ($names -contains "$modelName`:latest")
        if ($matched) {
            Write-Pass "Ollama baked model present: $modelName"
            # Generate smoke: prove the baked Gemma model actually loads and runs offline,
            # not just that it appears in the tag list.
            try {
                $genBody = @{
                    model       = $modelName
                    prompt      = "ping"
                    stream      = $false
                    options     = @{ num_predict = 1 }
                } | ConvertTo-Json -Compress
                $gen = Invoke-RestMethod -Uri "$ollamaUrl/api/generate" -Method Post -Body $genBody -ContentType "application/json" -TimeoutSec ([Math]::Max($TimeoutSec, 120))
                if ($null -ne $gen -and ($gen.PSObject.Properties.Name -contains "response")) {
                    Write-Pass "Ollama model '$modelName' generated a response (loads and runs offline)"
                } else {
                    Write-Fail "Ollama generate returned no response for '$modelName': $($gen | ConvertTo-Json -Compress)"
                    $failures++
                }
            } catch {
                Write-Fail "Ollama generate smoke failed for '$modelName' - $_"
                $failures++
            }
        } else {
            Write-Fail "Configured Ollama model '$modelName' not baked in. Available: $($names -join ', ')"
            $failures++
        }
    }
} catch {
    Write-Fail "Ollama probe failed at $ollamaUrl - $_"
    $failures++
}

# --- 8. Restart policy (containers survive a host reboot without re-running install) ---
$restartTargets = @()
if ($containerName) { $restartTargets += $containerName }
$ollamaName = if ($ollamaContainer) { ($ollamaContainer | Select-Object -First 1).Trim() } else { "" }
if ($ollamaName) { $restartTargets += $ollamaName }
foreach ($svc in $restartTargets) {
    $policy = (& $docker inspect $svc --format "{{.HostConfig.RestartPolicy.Name}}" 2>$null | Out-String).Trim()
    if ($policy -in @("unless-stopped", "always")) {
        Write-Pass "Restart policy '$policy' on ${svc} (auto-starts with Docker Desktop after reboot)"
    } else {
        Write-Fail "Restart policy on ${svc} is '$policy' (expected unless-stopped) - will not auto-start after reboot"
        $failures++
    }
}

# --- Summary ---
if ($failures -eq 0) {
    Write-Host ""
    Write-Host "[accept] All checks passed." -ForegroundColor Green
    exit 0
}

Write-Host ""
Write-Host "[accept] $failures check(s) failed." -ForegroundColor Red
exit 1
