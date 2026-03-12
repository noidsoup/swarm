#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Sets up OpenSSH Server on Windows for remote AI compute access.
.DESCRIPTION
    Installs OpenSSH Server, configures key-based auth, sets PowerShell as
    default shell, and opens firewall port 22.
    Run this script once from an elevated (Admin) PowerShell.
#>

param(
    [string]$DefaultShell = "C:\Program Files\PowerShell\7\pwsh.exe"
)

$ErrorActionPreference = "Stop"

Write-Host "`n=== Phase 0.1: SSH Server Setup ===" -ForegroundColor Cyan

# 1. Install OpenSSH Server
$sshCapability = Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'
if ($sshCapability.State -ne 'Installed') {
    Write-Host "[1/6] Installing OpenSSH Server..."
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
} else {
    Write-Host "[1/6] OpenSSH Server already installed." -ForegroundColor Green
}

# 2. Start and auto-start sshd
Write-Host "[2/6] Starting sshd service..."
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic

# 3. Set default shell to PowerShell 7 (or fallback to Windows PowerShell)
if (-not (Test-Path $DefaultShell)) {
    $DefaultShell = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    Write-Host "  PowerShell 7 not found, using Windows PowerShell"
}
Write-Host "[3/6] Setting default SSH shell to: $DefaultShell"
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell `
    -Value $DefaultShell -PropertyType String -Force | Out-Null

# 4. Firewall rule
$existingRule = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
if (-not $existingRule) {
    Write-Host "[4/6] Creating firewall rule for port 22..."
    New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" `
        -DisplayName "OpenSSH Server (sshd)" `
        -Enabled True -Direction Inbound -Protocol TCP `
        -Action Allow -LocalPort 22 | Out-Null
} else {
    Write-Host "[4/6] Firewall rule already exists." -ForegroundColor Green
}

# 5. Create .ssh directory and authorized_keys for current user
$sshDir = "$env:USERPROFILE\.ssh"
$authKeys = "$sshDir\authorized_keys"
if (-not (Test-Path $sshDir)) {
    New-Item -ItemType Directory -Path $sshDir -Force | Out-Null
}
if (-not (Test-Path $authKeys)) {
    New-Item -ItemType File -Path $authKeys -Force | Out-Null
    Write-Host "[5/6] Created $authKeys — paste your Mac's public key here."
} else {
    Write-Host "[5/6] $authKeys already exists." -ForegroundColor Green
}

# 6. Fix permissions on authorized_keys (Windows OpenSSH requirement for admin users)
$acl = Get-Acl $authKeys
$acl.SetAccessRuleProtection($true, $false)
$adminRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    "BUILTIN\Administrators", "FullControl", "Allow")
$systemRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    "SYSTEM", "FullControl", "Allow")
$acl.SetAccessRule($adminRule)
$acl.SetAccessRule($systemRule)
Set-Acl -Path $authKeys -AclObject $acl

# For admin users, OpenSSH on Windows uses administrators_authorized_keys
$adminAuthKeys = "C:\ProgramData\ssh\administrators_authorized_keys"
if (-not (Test-Path $adminAuthKeys)) {
    Copy-Item $authKeys $adminAuthKeys -Force
    $acl2 = Get-Acl $adminAuthKeys
    $acl2.SetAccessRuleProtection($true, $false)
    $acl2.SetAccessRule($adminRule)
    $acl2.SetAccessRule($systemRule)
    Set-Acl -Path $adminAuthKeys -AclObject $acl2
    Write-Host "  Also created $adminAuthKeys for admin user SSH."
}

Write-Host "[6/6] Verifying sshd is running..."
$svc = Get-Service sshd
Write-Host "  sshd status: $($svc.Status) | StartType: $($svc.StartType)" -ForegroundColor Green

# Show IP addresses for Mac connection
Write-Host "`n=== Connection Info ===" -ForegroundColor Yellow
Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.InterfaceAlias -notmatch "Loopback" -and $_.IPAddress -ne "127.0.0.1"
} | ForEach-Object {
    Write-Host "  ssh $env:USERNAME@$($_.IPAddress)"
}

Write-Host "`n=== Next Steps ===" -ForegroundColor Yellow
Write-Host "  1. On your Mac: ssh-keygen -t ed25519 -C 'mac-to-windows'"
Write-Host "  2. Copy the public key content from ~/.ssh/id_ed25519.pub"
Write-Host "  3. Paste it into: $adminAuthKeys"
Write-Host "  4. Test: ssh $env:USERNAME@<IP_FROM_ABOVE>"
Write-Host "`nDone!" -ForegroundColor Green
