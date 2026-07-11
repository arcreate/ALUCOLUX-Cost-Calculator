# Upload changed app files and restart alucolux (run setup_ssh_alucolux.ps1 first).
# Before upload: backs up current code to /opt/alucolux_prev on the server.
param(
    [string]$HostAlias = "alucolux",
    [string]$RemotePath = "/opt/alucolux",
    [switch]$NoRestart,
    [switch]$SkipBackup
)

$Root = Split-Path $PSScriptRoot -Parent
$BackupSh = Join-Path $Root "scripts\server_backup_prev.sh"
$RollbackSh = Join-Path $Root "scripts\server_rollback_prev.sh"

ssh $HostAlias "mkdir -p ${RemotePath}/scripts ${RemotePath}/hermes/alucolux-quote"
scp $BackupSh $RollbackSh "${HostAlias}:${RemotePath}/scripts/"
ssh $HostAlias "sed -i 's/\r$//' ${RemotePath}/scripts/server_backup_prev.sh ${RemotePath}/scripts/server_rollback_prev.sh 2>/dev/null; chmod +x ${RemotePath}/scripts/server_backup_prev.sh ${RemotePath}/scripts/server_rollback_prev.sh"

if (-not $SkipBackup) {
    Write-Host "Backing up current version to ${RemotePath}_prev ..."
    ssh $HostAlias "chmod +x ${RemotePath}/scripts/server_backup_prev.sh && bash ${RemotePath}/scripts/server_backup_prev.sh"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Backup failed. Deploy aborted (use -SkipBackup to override)."
        exit 1
    }
}

$Files = @(
    @{ Local = "app.py"; Remote = "$RemotePath/" },
    @{ Local = "core\calculator.py"; Remote = "$RemotePath/core/" },
    @{ Local = "core\coating.py"; Remote = "$RemotePath/core/" },
    @{ Local = "core\reporting.py"; Remote = "$RemotePath/core/" },
    @{ Local = "core\storage.py"; Remote = "$RemotePath/core/" },
    @{ Local = "core\auth.py"; Remote = "$RemotePath/core/" },
    @{ Local = "core\optimizer.py"; Remote = "$RemotePath/core/" },
    @{ Local = "core\paths.py"; Remote = "$RemotePath/core/" },
    @{ Local = "core\interactive_report.py"; Remote = "$RemotePath/core/" },
    @{ Local = "core\agent_bundle.py"; Remote = "$RemotePath/core/" },
    @{ Local = "core\price_matrix.py"; Remote = "$RemotePath/core/" },
    @{ Local = "core\ui_draft.py"; Remote = "$RemotePath/core/" },
    @{ Local = "core\vars_campaign.py"; Remote = "$RemotePath/core/" },
    @{ Local = "core\production_limits.py"; Remote = "$RemotePath/core/" },
    @{ Local = "hermes\alucolux-quote\SKILL.md"; Remote = "$RemotePath/hermes/alucolux-quote/" },
    @{ Local = "hermes\alucolux-quote\reference.md"; Remote = "$RemotePath/hermes/alucolux-quote/" },
    @{ Local = "scripts\server_setup_https.sh"; Remote = "$RemotePath/scripts/" },
    @{ Local = "scripts\server_add_https_domain.sh"; Remote = "$RemotePath/scripts/" }
)

foreach ($f in $Files) {
    $src = Join-Path $Root $f.Local
    if (-not (Test-Path $src)) {
        Write-Warning "Skip missing: $($f.Local)"
        continue
    }
    Write-Host "Upload $($f.Local) -> ${HostAlias}:$($f.Remote)"
    scp $src "${HostAlias}:$($f.Remote)"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Upload failed: $($f.Local). Run .\scripts\setup_ssh_alucolux.ps1 first."
        exit 1
    }
}

if (-not $NoRestart) {
    Write-Host "Restarting alucolux ..."
    ssh $HostAlias "systemctl restart alucolux && systemctl is-active alucolux"
}

Write-Host "Done. Refresh http://47.102.222.183"
Write-Host "If broken: .\scripts\rollback_server.ps1"
