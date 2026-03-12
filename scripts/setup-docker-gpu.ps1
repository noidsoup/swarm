#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Verifies Docker Desktop + WSL2 + NVIDIA GPU passthrough are working.
.DESCRIPTION
    Checks WSL2 installation, Docker daemon, and GPU access from containers.
    Run from elevated PowerShell after Docker Desktop is installed and running.
#>

$ErrorActionPreference = "Stop"

Write-Host "`n=== Phase 0.2: Docker + GPU Verification ===" -ForegroundColor Cyan

# 1. Check WSL2
Write-Host "[1/5] Checking WSL2..."
$wslVersion = wsl --status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  WSL not found. Installing WSL2..."
    wsl --install --no-distribution
    wsl --set-default-version 2
    Write-Host "  WSL2 installed. You may need to reboot." -ForegroundColor Yellow
} else {
    Write-Host "  WSL2 is installed." -ForegroundColor Green
}

# 2. Check Docker daemon
Write-Host "[2/5] Checking Docker daemon..."
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Docker daemon not running!" -ForegroundColor Red
    Write-Host "  Start Docker Desktop and re-run this script."
    Write-Host "  Tip: Settings > General > 'Start Docker Desktop when you sign in'"
    exit 1
}
Write-Host "  Docker daemon is running." -ForegroundColor Green

# 3. Check Docker is using WSL2 backend
Write-Host "[3/5] Checking Docker backend..."
if ($dockerInfo -match "WSL") {
    Write-Host "  Docker is using WSL2 backend." -ForegroundColor Green
} else {
    Write-Host "  Docker may not be using WSL2. Check Docker Desktop settings." -ForegroundColor Yellow
}

# 4. Test basic container
Write-Host "[4/5] Running hello-world container..."
docker run --rm hello-world 2>&1 | Select-Object -First 3
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Container execution works." -ForegroundColor Green
} else {
    Write-Host "  Container test failed!" -ForegroundColor Red
    exit 1
}

# 5. Test GPU passthrough
Write-Host "[5/5] Testing GPU passthrough..."
Write-Host "  Pulling nvidia/cuda base image (first time takes a minute)..."
$gpuTest = docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host $gpuTest
    Write-Host "`n  GPU passthrough works!" -ForegroundColor Green
} else {
    Write-Host "  GPU passthrough failed." -ForegroundColor Red
    Write-Host "  Ensure:"
    Write-Host "    1. Docker Desktop > Settings > Resources > Enable GPU"
    Write-Host "    2. NVIDIA drivers are up to date (you have 581.32)"
    Write-Host "    3. WSL2 has NVIDIA CUDA support"
    Write-Host "  Error: $gpuTest"
    exit 1
}

Write-Host "`n=== All checks passed! ===" -ForegroundColor Green
Write-Host "  Docker + GPU ready for Ollama containers."
