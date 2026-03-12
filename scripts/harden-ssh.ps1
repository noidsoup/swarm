#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Harden OpenSSH Server: disable password auth, restrict to key-only.
.DESCRIPTION
    Run after setup-ssh-server.ps1 and verifying key-based login works.
    WARNING: If your key isn't set up, you'll lock yourself out!
#>

$ErrorActionPreference = "Stop"
$sshdConfig = "C:\ProgramData\ssh\sshd_config"

Write-Host "`n=== Hardening SSH ===" -ForegroundColor Cyan

# Backup
$backup = "${sshdConfig}.bak.$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Copy-Item $sshdConfig $backup
Write-Host "Backed up config to: $backup"

$content = Get-Content $sshdConfig -Raw

$replacements = @{
    '#?PasswordAuthentication\s+yes'  = 'PasswordAuthentication no'
    '#?PermitEmptyPasswords\s+yes'    = 'PermitEmptyPasswords no'
    '#?PubkeyAuthentication\s+.*'     = 'PubkeyAuthentication yes'
    '#?MaxAuthTries\s+\d+'            = 'MaxAuthTries 3'
}

foreach ($pattern in $replacements.Keys) {
    if ($content -match $pattern) {
        $content = $content -replace $pattern, $replacements[$pattern]
    }
}

Set-Content $sshdConfig $content

Restart-Service sshd
Write-Host "sshd restarted with hardened config." -ForegroundColor Green
Write-Host ""
Write-Host "Changes applied:"
Write-Host "  - PasswordAuthentication no"
Write-Host "  - PermitEmptyPasswords no"
Write-Host "  - PubkeyAuthentication yes"
Write-Host "  - MaxAuthTries 3"
Write-Host ""
Write-Host "TEST your key login from Mac BEFORE closing this session!" -ForegroundColor Yellow
