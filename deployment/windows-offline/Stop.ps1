$ErrorActionPreference = 'Continue'
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Push-Location (Join-Path $packageRoot 'app')
docker compose -f compose.portable.yaml stop
Pop-Location

Push-Location (Join-Path $packageRoot 'dify\docker')
docker compose stop
Pop-Location

docker stop ollama *> $null
Write-Host '服務已停止，資料仍完整保留。'
