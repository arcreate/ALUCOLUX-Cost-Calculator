# Roll back server to previous code backup (/opt/alucolux_prev).
param(
    [string]$HostAlias = "alucolux",
    [string]$RemotePath = "/opt/alucolux"
)

$Root = Split-Path $PSScriptRoot -Parent
$RollbackSh = Join-Path $Root "scripts\server_rollback_prev.sh"

Write-Host "Rolling back on ${HostAlias} ..."
scp $RollbackSh "${HostAlias}:${RemotePath}/scripts/server_rollback_prev.sh"
ssh $HostAlias "chmod +x ${RemotePath}/scripts/server_rollback_prev.sh && bash ${RemotePath}/scripts/server_rollback_prev.sh"
if ($LASTEXITCODE -eq 0) {
    Write-Host "Rollback done. Refresh http://47.102.222.183"
} else {
    Write-Error "Rollback failed."
    exit 1
}
