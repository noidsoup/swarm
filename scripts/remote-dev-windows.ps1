# Daily helper for Windows execution machine (called from Windows PowerShell).
# Usage:
#   .\scripts\remote-dev-windows.ps1 start-dev
#   .\scripts\remote-dev-windows.ps1 start-smoke
#   .\scripts\remote-dev-windows.ps1 stop
#   .\scripts\remote-dev-windows.ps1 status

param(
    [Parameter(Position = 0)]
    [ValidateSet("start-dev", "start-smoke", "stop", "status", "restart-dev")]
    [string]$Command = "status"
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $RepoRoot) { $RepoRoot = (Get-Location).Path }
$WorkerScript = Join-Path $RepoRoot "scripts\cursor-worker.ps1"

if (-not (Test-Path $WorkerScript)) {
    Write-Error "Missing worker helper script: $WorkerScript"
    exit 1
}

function Start-DevWorker {
    Push-Location $RepoRoot
    try {
        Remove-Item Env:\SWARM_SMOKE_SKIP_LLM -ErrorAction SilentlyContinue
        if (-not $env:WINDOWS_CURSOR_TASK_TIMEOUT) { $env:WINDOWS_CURSOR_TASK_TIMEOUT = "900" }
        if (-not $env:OLLAMA_KEEP_ALIVE) { $env:OLLAMA_KEEP_ALIVE = "30m" }
        & powershell -ExecutionPolicy Bypass -File $WorkerScript stop | Out-Null
        & powershell -ExecutionPolicy Bypass -File $WorkerScript start
        Write-Host "Dev mode ready (real LLM path)."
        Write-Host "WINDOWS_CURSOR_TASK_TIMEOUT=$env:WINDOWS_CURSOR_TASK_TIMEOUT"
        Write-Host "OLLAMA_KEEP_ALIVE=$env:OLLAMA_KEEP_ALIVE"
    } finally {
        Pop-Location
    }
}

function Start-SmokeWorker {
    Push-Location $RepoRoot
    try {
        & powershell -ExecutionPolicy Bypass -File $WorkerScript stop | Out-Null
        & powershell -ExecutionPolicy Bypass -File $WorkerScript start -Fast
        Write-Host "Smoke mode ready (skip-LLM path)."
    } finally {
        Pop-Location
    }
}

switch ($Command) {
    "start-dev" {
        Start-DevWorker
    }
    "start-smoke" {
        Start-SmokeWorker
    }
    "restart-dev" {
        Start-DevWorker
    }
    "stop" {
        & powershell -ExecutionPolicy Bypass -File $WorkerScript stop
    }
    "status" {
        & powershell -ExecutionPolicy Bypass -File $WorkerScript status
    }
}
