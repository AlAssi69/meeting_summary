<#
.SYNOPSIS
    Clean up residual Docker artifacts from a previous (possibly failed) offline
    Meeting Assistant install on the target machine.

.DESCRIPTION
    Tears down the compose stack and removes the meeting-assistant containers,
    network, and the .active_profile marker so install_from_usb.ps1 can start fresh.

    By default this is conservative: it stops/removes containers and the compose
    network but KEEPS the loaded Docker images and the Ollama runtime volume, and
    NEVER touches your host data (data\ and meeting_outputs\).

    Use the switches below for a deeper clean:
      -RemoveImages   also delete the meeting-assistant:* images (next install
                      must re-load them from the .tar files in images\).
      -RemoveVolumes  also delete the Ollama runtime volume.
      -PruneBuilder   also prune dangling images and Docker build cache.
      -All            shorthand for -RemoveImages -RemoveVolumes -PruneBuilder.

.EXAMPLE
    .\clean_install.ps1
    Stop and remove containers + network only (safe, quick reset).

.EXAMPLE
    .\clean_install.ps1 -All
    Full reset, including images, volume, and build cache.
#>
param(
    [string]$BundleDir = (Resolve-Path ".").Path,
    [switch]$RemoveImages,
    [switch]$RemoveVolumes,
    [switch]$PruneBuilder,
    [switch]$All
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

if ($All) {
    $RemoveImages = $true
    $RemoveVolumes = $true
    $PruneBuilder = $true
}

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "=== $Message ===" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[clean] $Message" -ForegroundColor Green
}

function Write-Skip {
    param([string]$Message)
    Write-Host "[clean] $Message" -ForegroundColor Yellow
}

# Run a docker command best-effort: never aborts the script, returns stdout/stderr text.
function Invoke-DockerQuiet {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$DockerArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & $docker @DockerArgs 2>&1
        $script:LastDockerExit = $LASTEXITCODE
        return ($out | Out-String).Trim()
    } finally {
        $ErrorActionPreference = $prev
    }
}

$bundleDir = (Resolve-Path $BundleDir).Path
$envPath = Join-Path $bundleDir ".env.bundle"
$baseCompose = Join-Path $bundleDir "compose\compose.yml"
$gpuCompose = Join-Path $bundleDir "compose\compose.gpu.yml"
$profilePath = Join-Path $bundleDir ".active_profile"

$containerNames = @("meeting-assistant-whisper", "meeting-assistant-ollama")
$imageRefs = @(
    "meeting-assistant:cpu-bundle",
    "meeting-assistant:gpu-bundle",
    "meeting-assistant:ollama-bundle"
)
$volumeMatch = "meeting_assistant_ollama"

Write-Host "Meeting Assistant - offline install cleanup" -ForegroundColor Cyan
Write-Host "Bundle dir : $bundleDir"
Write-Host "Docker CLI : $docker"
Write-Host "Options    : RemoveImages=$RemoveImages RemoveVolumes=$RemoveVolumes PruneBuilder=$PruneBuilder"

# --- 1. Compose teardown -----------------------------------------------------
Write-Step "Stopping compose stack"
if (Test-Path $baseCompose) {
    $composeArgs = [System.Collections.Generic.List[string]]::new()
    $composeArgs.Add("compose")
    if (Test-Path $envPath) {
        $composeArgs.Add("--env-file"); $composeArgs.Add($envPath)
    }
    $composeArgs.Add("-f"); $composeArgs.Add($baseCompose)
    if (Test-Path $gpuCompose) {
        $composeArgs.Add("-f"); $composeArgs.Add($gpuCompose)
    }
    $composeArgs.Add("down")
    $composeArgs.Add("--remove-orphans")
    if ($RemoveVolumes) { $composeArgs.Add("-v") }
    if ($RemoveImages) { $composeArgs.Add("--rmi"); $composeArgs.Add("all") }

    $composeArgArray = $composeArgs.ToArray()
    $out = Invoke-DockerQuiet @composeArgArray
    if ($out) { Write-Host $out }
    Write-Ok "compose down complete."
} else {
    Write-Skip "compose.yml not found at $baseCompose - skipping compose down (will remove containers by name)."
}

# --- 2. Remove leftover containers by name -----------------------------------
Write-Step "Removing leftover containers"
foreach ($name in $containerNames) {
    $id = Invoke-DockerQuiet ps -aq --filter "name=^/$name$"
    if ($id) {
        Invoke-DockerQuiet rm -f $name | Out-Null
        Write-Ok "Removed container $name."
    } else {
        Write-Skip "Container $name not present."
    }
}

# --- 3. Remove images (opt-in) -----------------------------------------------
if ($RemoveImages) {
    Write-Step "Removing meeting-assistant images"
    foreach ($ref in $imageRefs) {
        $exists = Invoke-DockerQuiet image inspect $ref --format "{{.Id}}"
        if ($script:LastDockerExit -eq 0 -and $exists) {
            Invoke-DockerQuiet rmi -f $ref | Out-Null
            Write-Ok "Removed image $ref."
        } else {
            Write-Skip "Image $ref not present."
        }
    }
} else {
    Write-Skip "Keeping loaded images (use -RemoveImages to delete them)."
}

# --- 4. Remove named volumes (opt-in) ----------------------------------------
if ($RemoveVolumes) {
    Write-Step "Removing Ollama runtime volume(s)"
    $volumes = Invoke-DockerQuiet volume ls -q
    $matched = @()
    if ($volumes) {
        $matched = $volumes -split "`n" | Where-Object { $_ -like "*$volumeMatch*" }
    }
    if ($matched.Count -gt 0) {
        foreach ($vol in $matched) {
            Invoke-DockerQuiet volume rm -f $vol | Out-Null
            Write-Ok "Removed volume $vol."
        }
    } else {
        Write-Skip "No volume matching *$volumeMatch* found."
    }
} else {
    Write-Skip "Keeping runtime volume (use -RemoveVolumes to delete it)."
}

# --- 5. Prune dangling images / build cache (opt-in) -------------------------
if ($PruneBuilder) {
    Write-Step "Pruning dangling images and build cache"
    Invoke-DockerQuiet image prune -f | Out-Null
    Write-Ok "Dangling images pruned."
    Invoke-DockerQuiet builder prune -f | Out-Null
    Write-Ok "Build cache pruned."
} else {
    Write-Skip "Skipping prune (use -PruneBuilder to reclaim dangling images / build cache)."
}

# --- 6. Remove the active-profile marker -------------------------------------
Write-Step "Clearing install markers"
if (Test-Path $profilePath) {
    Remove-Item -Path $profilePath -Force
    Write-Ok "Removed .active_profile marker."
} else {
    Write-Skip ".active_profile marker not present."
}

Write-Host ""
Write-Host "[clean] Cleanup complete. Host data (data\, meeting_outputs\) was left untouched." -ForegroundColor Green
Write-Host "[clean] Re-run install_from_usb.ps1 to reinstall." -ForegroundColor Green
