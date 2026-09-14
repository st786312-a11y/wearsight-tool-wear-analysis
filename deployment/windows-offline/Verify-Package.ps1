$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$manifestPath = Join-Path $packageRoot 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw '找不到 manifest.json。' }

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$failed = $false
foreach ($artifact in $manifest.artifacts) {
    $path = Join-Path $packageRoot ($artifact.file -replace '/', '\')
    if (-not (Test-Path -LiteralPath $path)) {
        Write-Host "[缺少] $($artifact.file)" -ForegroundColor Red
        $failed = $true
        continue
    }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -eq $artifact.sha256) {
        Write-Host "[正常] $($artifact.file)" -ForegroundColor Green
    } else {
        Write-Host "[損壞] $($artifact.file)" -ForegroundColor Red
        $failed = $true
    }
}
if ($failed) { throw '部署包檢查失敗，請重新複製。' }
Write-Host '部署包檢查完成，所有大型檔案均完整。'
