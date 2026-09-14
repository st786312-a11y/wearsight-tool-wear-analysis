$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backupRoot = Join-Path $packageRoot 'backups'
$imageArchive = Join-Path $packageRoot 'images\docker-images.tar'

function Assert-DockerReady {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw '找不到 Docker。請先安裝並開啟 Docker Desktop，再重新執行此檔案。'
    }
    docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Desktop 尚未啟動。請開啟 Docker Desktop，等待引擎完成啟動後再試一次。'
    }
}

function Restore-Volume([string]$volumeName, [string]$archiveName) {
    $archivePath = Join-Path $backupRoot $archiveName
    if (-not (Test-Path -LiteralPath $archivePath)) {
        throw "缺少模型封存檔：$archivePath"
    }
    docker volume create $volumeName | Out-Null
    $hasData = docker run --rm -v "${volumeName}:/data" busybox:latest sh -c 'test -n "$(ls -A /data 2>/dev/null)"; echo $?'
    if (($hasData | Select-Object -Last 1).Trim() -eq '0') {
        Write-Host "略過 $volumeName：目的卷已有資料。"
        return
    }
    docker run --rm -v "${volumeName}:/restore" -v "${backupRoot}:/backup:ro" busybox:latest sh -c "tar xzf /backup/$archiveName -C /restore"
    if ($LASTEXITCODE -ne 0) { throw "還原 $volumeName 失敗。" }
}

Assert-DockerReady
if (-not (Test-Path -LiteralPath $imageArchive)) {
    throw "缺少 Docker 映像封存檔：$imageArchive"
}

Write-Host '載入離線映像，第一次約需數分鐘……'
docker load -i $imageArchive
if ($LASTEXITCODE -ne 0) { throw '載入 Docker 映像失敗。' }

$difyCompose = Join-Path $packageRoot 'dify\docker\docker-compose.yaml'
if (-not (Test-Path -LiteralPath $difyCompose)) {
    $difyArchive = Join-Path $backupRoot 'dify-docker.tar.gz'
    if (-not (Test-Path -LiteralPath $difyArchive)) { throw "缺少 Dify 封存檔：$difyArchive" }
    New-Item -ItemType Directory -Path (Join-Path $packageRoot 'dify') -Force | Out-Null
    docker run --rm -v "${packageRoot}:/package" busybox:latest sh -c 'tar xzf /package/backups/dify-docker.tar.gz -C /package/dify'
    if ($LASTEXITCODE -ne 0) { throw '還原 Dify 資料失敗。' }
}

$difyEnv = Join-Path $packageRoot 'dify\docker\.env'
if (Test-Path -LiteralPath $difyEnv) {
    $envText = Get-Content -LiteralPath $difyEnv -Raw
    $envText = [regex]::Replace($envText, '(?m)^EXPOSE_NGINX_PORT=.*$', 'EXPOSE_NGINX_PORT=8081')
    $envText = [regex]::Replace($envText, '(?m)^EXPOSE_NGINX_SSL_PORT=.*$', 'EXPOSE_NGINX_SSL_PORT=8443')
    Set-Content -LiteralPath $difyEnv -Value $envText -Encoding utf8
}

Restore-Volume 'wearsight-model-cache' 'dinov2-model-cache.tar.gz'
Restore-Volume 'ollama' 'ollama-models.tar.gz'

& (Join-Path $packageRoot 'Start.ps1')
Write-Host ''
Write-Host '安裝完成。主系統：http://localhost:8080'
Write-Host 'Dify：http://localhost:8081'
