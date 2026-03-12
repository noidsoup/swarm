# Start/stop the cursor worker daemon for Mac->Windows smoke tests.
# Usage: .\scripts\cursor-worker.ps1 start [--fast]
#        .\scripts\cursor-worker.ps1 stop
#        .\scripts\cursor-worker.ps1 status
# --fast: set SWARM_SMOKE_SKIP_LLM=1 and 60s timeout for quick pipeline check.

param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "status")]
    [string]$Command = "status",

    [switch]$Fast
)

$PidFile = "$env:TEMP\swarm-worker.pid"
$LogFile = "$env:TEMP\swarm-worker.log"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $RepoRoot) { $RepoRoot = (Get-Location).Path }

function Get-WorkerPid {
    if (Test-Path $PidFile) {
        $p = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($p -match '^\d+$') { return [int]$p }
    }
    return $null
}

function Stop-Worker {
    $p = Get-WorkerPid
    if ($p) {
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        Write-Host "Stopped worker PID $p"
    } else {
        Write-Host "No worker PID file found at $PidFile"
    }
}

function Show-Status {
    $p = Get-WorkerPid
    if ($p) {
        $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "Worker running PID $p"
            return
        }
    }
    Write-Host "Worker not running"
}

function Start-Worker {
    $p = Get-WorkerPid
    if ($p) {
        $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "Worker already running PID $p"
            return
        }
    }

    if ($Fast) {
        $env:SWARM_SMOKE_SKIP_LLM = "1"
        $env:WINDOWS_CURSOR_TASK_TIMEOUT = "60"
        $Timeout = 60
    } else {
        # Real LLM run: 600s so Windows Ollama has time to finish build phase
        $env:WINDOWS_CURSOR_TASK_TIMEOUT = "600"
        $Timeout = 600
    }

    Push-Location $RepoRoot
    try {
        $newPid = python scripts/cursor_worker.py --daemon --poll-interval 2 --task-timeout $Timeout --log-file $LogFile --pid-file $PidFile
        Write-Host "Started worker PID $newPid (timeout ${Timeout}s)"
        if ($Fast) { Write-Host "Fast smoke: SWARM_SMOKE_SKIP_LLM=1" }
    } finally {
        Pop-Location
    }
}

switch ($Command) {
    start  { Start-Worker }
    stop   { Stop-Worker }
    status { Show-Status }
}
