# 上传 deploy_upload 到阿里云服务器（仅运行所需文件）
# 用法：在 PowerShell 中执行：
#   cd "C:\Users\liwen\Desktop\ALUCOLUX Cost Calculator"
#   .\scripts\upload_deploy.ps1
# 或指定 IP：
#   .\scripts\upload_deploy.ps1 -ServerIP 47.102.222.183

param(
    [string]$HostAlias = "alucolux",
    [string]$ServerIP = "47.102.222.183",
    [string]$RemotePath = "/opt/alucolux"
)

$Root = Split-Path $PSScriptRoot -Parent
$Deploy = Join-Path $Root "deploy_upload"
$Target = $HostAlias
if ($HostAlias -eq "alucolux") {
    $sshTest = ssh -o BatchMode=yes -o ConnectTimeout=5 $HostAlias "echo ok" 2>$null
    if ($LASTEXITCODE -ne 0) {
        $Target = "root@${ServerIP}"
        Write-Warning "未检测到 Host alucolux 免密，将使用 ${Target}（可能需要密码）。可先运行 .\scripts\setup_ssh_alucolux.ps1"
    }
} else {
    $Target = "root@${ServerIP}"
}

if (-not (Test-Path "$Deploy\app.py")) {
    Write-Error "未找到 deploy_upload，请先运行整理部署包步骤。"
    exit 1
}

Write-Host "上传 $Deploy -> ${Target}:${RemotePath}/"
ssh "${Target}" "mkdir -p ${RemotePath}"
scp -r "$Deploy\*" "${Target}:${RemotePath}/"
if ($LASTEXITCODE -eq 0) {
    Write-Host "上传完成。请在服务器执行: bash ${RemotePath}/scripts/server_setup.sh"
} else {
    Write-Error "上传失败，请检查 SSH 与网络。"
    exit 1
}
