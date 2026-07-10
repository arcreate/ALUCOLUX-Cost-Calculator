# One-time: install SSH public key on Aliyun ECS for passwordless login.
# Usage:
#   cd "C:\Users\liwen\Desktop\ALUCOLUX Cost Calculator"
#   .\scripts\setup_ssh_alucolux.ps1
#
# Enter root password when prompted (once). Do not share password in chat.

param(
    [string]$ServerIP = "47.102.222.183",
    [string]$HostAlias = "alucolux",
    [string]$KeyPath = "$env:USERPROFILE\.ssh\id_ed25519_alucolux"
)

$ErrorActionPreference = "Stop"
$SshDir = "$env:USERPROFILE\.ssh"
$PubPath = "$KeyPath.pub"

New-Item -ItemType Directory -Force -Path $SshDir | Out-Null

if (-not (Test-Path $KeyPath)) {
    Write-Host "Generating key: $KeyPath"
    ssh-keygen -t ed25519 -f $KeyPath -N "" -C "alucolux-deploy"
}

$configPath = Join-Path $SshDir "config"
$block = @"

Host $HostAlias
    HostName $ServerIP
    User root
    IdentityFile $KeyPath
    IdentitiesOnly yes

"@

if (-not (Test-Path $configPath)) {
    Set-Content -Path $configPath -Value $block.TrimStart() -Encoding ascii
    Write-Host "Created $configPath"
} elseif (-not (Select-String -Path $configPath -Pattern "Host\s+$HostAlias" -Quiet)) {
    Add-Content -Path $configPath -Value $block -Encoding ascii
    Write-Host "Appended Host $HostAlias to $configPath"
} else {
    Write-Host "Host $HostAlias already in SSH config, skipped."
}

Write-Host ""
Write-Host "Uploading public key to root@${ServerIP} ..."
Write-Host "Enter root password when prompted (input is hidden)."
Write-Host ""

Get-Content $PubPath -Raw | ssh -o StrictHostKeyChecking=accept-new "root@${ServerIP}" "umask 077; mkdir -p .ssh; cat >> .ssh/authorized_keys; chmod 700 .ssh; chmod 600 .ssh/authorized_keys 2>/dev/null; sort -u .ssh/authorized_keys -o .ssh/authorized_keys"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to upload public key. Check IP, password, and network."
    exit 1
}

Write-Host ""
Write-Host "Testing passwordless login..."
ssh -o BatchMode=yes $HostAlias "echo SSH_OK; hostname"
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "OK. You can now use:"
    Write-Host "  ssh $HostAlias"
    Write-Host "  .\scripts\upload_changed.ps1"
} else {
    Write-Warning "Key may not be active. Retry or check /root/.ssh/authorized_keys on server."
    exit 1
}
