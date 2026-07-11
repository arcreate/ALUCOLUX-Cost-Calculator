# Upload Quote API files and run server_setup_api.sh on ECS.
param(
    [string]$HostAlias = "alucolux",
    [string]$RemotePath = "/opt/alucolux"
)

$Root = Split-Path $PSScriptRoot -Parent

$Files = @(
    @{ Local = "api\__init__.py"; Remote = "$RemotePath/api/" },
    @{ Local = "api\config.py"; Remote = "$RemotePath/api/" },
    @{ Local = "api\schemas.py"; Remote = "$RemotePath/api/" },
    @{ Local = "api\service.py"; Remote = "$RemotePath/api/" },
    @{ Local = "api\deps.py"; Remote = "$RemotePath/api/" },
    @{ Local = "api\main.py"; Remote = "$RemotePath/api/" },
    @{ Local = "core\calculator.py"; Remote = "$RemotePath/core/" },
    @{ Local = "core\coating.py"; Remote = "$RemotePath/core/" },
    @{ Local = "core\production_limits.py"; Remote = "$RemotePath/core/" },
    @{ Local = "core\paths.py"; Remote = "$RemotePath/core/" },
    @{ Local = "core\storage.py"; Remote = "$RemotePath/core/" },
    @{ Local = "core\auth.py"; Remote = "$RemotePath/core/" },
    @{ Local = "requirements-api.txt"; Remote = "$RemotePath/" },
    @{ Local = "scripts\server\alucolux-api.service"; Remote = "$RemotePath/scripts/server/" },
    @{ Local = "scripts\server\nginx\alucolux.conf"; Remote = "$RemotePath/scripts/server/nginx/" },
    @{ Local = "scripts\server_setup_api.sh"; Remote = "$RemotePath/scripts/" }
)

ssh $HostAlias "mkdir -p ${RemotePath}/api ${RemotePath}/core ${RemotePath}/scripts/server/nginx"

foreach ($f in $Files) {
    $src = Join-Path $Root $f.Local
    if (-not (Test-Path $src)) {
        Write-Error "Missing: $($f.Local)"
        exit 1
    }
    Write-Host "Upload $($f.Local) -> ${HostAlias}:$($f.Remote)"
    scp $src "${HostAlias}:$($f.Remote)"
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

Write-Host "Running server_setup_api.sh ..."
ssh $HostAlias "sed -i 's/\r$//' ${RemotePath}/scripts/server_setup_api.sh; chmod +x ${RemotePath}/scripts/server_setup_api.sh; bash ${RemotePath}/scripts/server_setup_api.sh"
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "Done. API health: http://alucolux.shenliwen.cc/api/health"
Write-Host "API key on server: ssh $HostAlias `"grep ALUCOLUX_API_KEY ${RemotePath}/.env.api`""
