#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Set up auto-start: Docker Desktop on login + compose services on boot.
#>

$ErrorActionPreference = "Stop"

Write-Host "`n=== Setting up auto-start ===" -ForegroundColor Cyan

# 1. Docker Desktop auto-start (check startup folder)
$dockerDesktopPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
$startupFolder = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startupFolder "Docker Desktop.lnk"

if (Test-Path $dockerDesktopPath) {
    if (-not (Test-Path $shortcutPath)) {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $dockerDesktopPath
        $shortcut.Arguments = "--minimize"
        $shortcut.Save()
        Write-Host "[1/2] Created Docker Desktop startup shortcut."
    } else {
        Write-Host "[1/2] Docker Desktop startup shortcut already exists." -ForegroundColor Green
    }
} else {
    Write-Host "[1/2] Docker Desktop not found at expected path." -ForegroundColor Yellow
}

# 2. Create a scheduled task to run docker compose up after Docker starts
# PSScriptRoot is "<repo>\scripts", so parent is the repo root.
$swarmRoot = Split-Path $PSScriptRoot -Parent
$taskName = "SwarmDockerComposeUp"
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if (-not $existingTask) {
    $action = New-ScheduledTaskAction `
        -Execute "cmd.exe" `
        -Argument "/c `"cd /d $swarmRoot && timeout /t 60 /nobreak && docker compose up -d`"" `
        -WorkingDirectory $swarmRoot

    $trigger = New-ScheduledTaskTrigger -AtLogon
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings `
        -Description "Start AI Dev Swarm Docker stack on login" | Out-Null

    Write-Host "[2/2] Created scheduled task: $taskName"
    Write-Host "  Waits 60s after login (for Docker to start), then runs docker compose up -d"
} else {
    Write-Host "[2/2] Scheduled task '$taskName' already exists." -ForegroundColor Green
}

Write-Host "`nAuto-start configured." -ForegroundColor Green
Write-Host "On reboot: Docker Desktop starts -> 60s delay -> docker compose up -d"
