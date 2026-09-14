param(
    [string]$PackageName = 'WearSight-Windows-Offline-20260908-v2'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$packageRoot = Join-Path $projectRoot $PackageName
$difySource = 'C:\Users\user\dify\docker'
$templateRoot = Join-Path $projectRoot 'deployment\windows-offline'
$servicesStopped = $false

function Invoke-Robocopy([string]$source, [string]$destination, [string[]]$extraArgs = @()) {
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    & robocopy $source $destination /E /R:2 /W:2 /NFL /NDL /NJH /NJS /NP @extraArgs
    if ($LASTEXITCODE -gt 7) { throw "複製失敗：$source" }
}

if (Test-Path -LiteralPath $packageRoot) {
    throw "輸出資料夾已存在，為避免覆寫已停止：$packageRoot"
}
if (-not (Test-Path -LiteralPath $difySource)) { throw "找不到 Dify：$difySource" }

New-Item -ItemType Directory -Path $packageRoot, (Join-Path $packageRoot 'app'), (Join-Path $packageRoot 'backups'), (Join-Path $packageRoot 'images') | Out-Null
Copy-Item -LiteralPath (Join-Path $templateRoot 'Install-Offline.ps1'), (Join-Path $templateRoot 'Start.ps1'), (Join-Path $templateRoot 'Stop.ps1'), (Join-Path $templateRoot 'Verify-Package.ps1'), (Join-Path $templateRoot 'README-WINDOWS.md') -Destination $packageRoot

$appRoot = Join-Path $packageRoot 'app'
Invoke-Robocopy (Join-Path $projectRoot 'backend') (Join-Path $appRoot 'backend') @('/XD', '__pycache__', '.pytest_cache')
Invoke-Robocopy (Join-Path $projectRoot 'frontend') (Join-Path $appRoot 'frontend') @('/XD', 'node_modules', 'dist')
Invoke-Robocopy (Join-Path $projectRoot 'dify') (Join-Path $appRoot 'dify')
Copy-Item -LiteralPath (Join-Path $projectRoot 'README.md'), (Join-Path $projectRoot '.env.example') -Destination $appRoot
Copy-Item -LiteralPath (Join-Path $templateRoot 'compose.portable.yaml') -Destination $appRoot

Write-Host '建立 Dify 資料庫備份……'
docker exec docker-db_postgres-1 sh -lc 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB" -f /tmp/dify-postgres.dump'
if ($LASTEXITCODE -ne 0) { throw 'Dify 資料庫備份失敗。' }
docker cp 'docker-db_postgres-1:/tmp/dify-postgres.dump' (Join-Path $packageRoot 'backups\dify-postgres.dump')

$apiImage = (docker inspect --format '{{.Image}}' project0528-api-1).Trim()
$frontendImage = (docker inspect --format '{{.Image}}' project0528-frontend-1).Trim()
docker image tag $apiImage 'wearsight-api:portable'
docker image tag $frontendImage 'wearsight-frontend:portable'

try {
    Write-Host '暫停服務並封存資料……'
    $servicesStopped = $true
    docker compose -f (Join-Path $projectRoot 'compose.yaml') stop
    docker stop ollama | Out-Null
    docker compose -f (Join-Path $difySource 'docker-compose.yaml') stop

    $backupRoot = Join-Path $packageRoot 'backups'
    docker run --rm -v 'C:\Users\user\dify:/source:ro' -v "${backupRoot}:/backup" busybox:latest tar czf /backup/dify-docker.tar.gz -C /source docker
    if ($LASTEXITCODE -ne 0) { throw 'Dify 完整資料封存失敗。' }
    docker run --rm -v 'project0528_clip-model-cache:/source:ro' -v "${backupRoot}:/backup" busybox:latest tar czf /backup/dinov2-model-cache.tar.gz -C /source .
    if ($LASTEXITCODE -ne 0) { throw 'DINOv2 模型快取封存失敗。' }
    docker run --rm -v 'ollama:/source:ro' -v "${backupRoot}:/backup" busybox:latest tar czf /backup/ollama-models.tar.gz -C /source .
    if ($LASTEXITCODE -ne 0) { throw 'Ollama 模型封存失敗。' }
} finally {
    if ($servicesStopped) {
        Write-Host '重新啟動本機服務……'
        docker compose -f (Join-Path $difySource 'docker-compose.yaml') up -d
        docker start ollama | Out-Null
        docker compose -f (Join-Path $projectRoot 'compose.yaml') up -d
    }
}

$images = @(
    'wearsight-api:portable',
    'wearsight-frontend:portable',
    'ollama/ollama:latest',
    'busybox:latest',
    'langgenius/dify-agent-backend:1.16.1',
    'langgenius/dify-agent-local-sandbox:1.16.1',
    'langgenius/dify-api:1.16.1',
    'langgenius/dify-plugin-daemon:0.6.3-local',
    'langgenius/dify-sandbox:0.2.15',
    'langgenius/dify-web:1.16.1',
    'nginx:latest',
    'postgres:15-alpine',
    'redis:6-alpine',
    'semitechnologies/weaviate:1.27.0',
    'ubuntu/squid:latest'
)

Write-Host '輸出離線 Docker 映像，這一步需要較長時間……'
docker image save --output (Join-Path $packageRoot 'images\docker-images.tar') $images
if ($LASTEXITCODE -ne 0) { throw 'Docker 映像封存失敗。' }

$artifactPaths = @(
    (Join-Path $packageRoot 'images\docker-images.tar'),
    (Join-Path $packageRoot 'backups\dify-docker.tar.gz'),
    (Join-Path $packageRoot 'backups\dinov2-model-cache.tar.gz'),
    (Join-Path $packageRoot 'backups\ollama-models.tar.gz'),
    (Join-Path $packageRoot 'backups\dify-postgres.dump')
)
$artifacts = foreach ($path in $artifactPaths) {
    $item = Get-Item -LiteralPath $path
    $hash = Get-FileHash -LiteralPath $path -Algorithm SHA256
    [pscustomobject]@{
        file = $item.FullName.Substring($packageRoot.Length + 1).Replace('\', '/')
        bytes = $item.Length
        sha256 = $hash.Hash.ToLowerInvariant()
    }
}
[pscustomobject]@{
    package = $PackageName
    created_at = (Get-Date).ToString('o')
    platform = 'Windows 10/11 Intel/AMD + Docker Desktop WSL2'
    includes = @('WearSight', 'DINOv2', 'YOLO', 'Dify 1.16.1 state', 'Ollama models')
    excludes = @('PPT', 'DINOv3 restricted weights')
    artifacts = $artifacts
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $packageRoot 'manifest.json') -Encoding utf8

$totalBytes = (Get-ChildItem -LiteralPath $packageRoot -Recurse -File | Measure-Object -Property Length -Sum).Sum
Write-Host "PACKAGE_PATH=$packageRoot"
Write-Host ("PACKAGE_SIZE_GB={0:N2}" -f ($totalBytes / 1GB))
