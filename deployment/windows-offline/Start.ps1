$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

docker info *> $null
if ($LASTEXITCODE -ne 0) { throw '請先啟動 Docker Desktop。' }
if (-not (Test-Path -LiteralPath (Join-Path $packageRoot 'dify\docker\docker-compose.yaml'))) {
    throw '尚未還原 Dify，請先執行 Install-Offline.ps1。'
}

Push-Location (Join-Path $packageRoot 'dify\docker')
try {
    docker compose up -d
    if ($LASTEXITCODE -ne 0) { throw 'Dify 啟動失敗。' }
} finally {
    Pop-Location
}

docker inspect ollama *> $null
if ($LASTEXITCODE -eq 0) {
    docker start ollama | Out-Null
} else {
    docker run -d --name ollama --restart unless-stopped -p 11434:11434 -v ollama:/root/.ollama ollama/ollama:latest | Out-Null
}
if ($LASTEXITCODE -ne 0) { throw 'Ollama 啟動失敗。' }

Push-Location (Join-Path $packageRoot 'app')
try {
    docker compose -f compose.portable.yaml up -d
    if ($LASTEXITCODE -ne 0) { throw '刀具磨耗系統啟動失敗。' }
} finally {
    Pop-Location
}

Write-Host '服務已啟動。'
Write-Host '主系統：http://localhost:8080'
Write-Host 'Dify：http://localhost:8081'
