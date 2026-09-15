param(
    [string]$SourceRoot = (Join-Path (Split-Path $PSScriptRoot -Parent) 'imports\HDR分類_四區間')
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$dataRoot = Join-Path $projectRoot 'backend\data'
$modelRoot = Join-Path $projectRoot 'backend\models'
$sourceWeight = Join-Path $SourceRoot 'keypoint_best.pt'
$casesPath = Join-Path $dataRoot 'cases.json'
$targetWeight = Join-Path $modelRoot 'keypoint-best.pt'
$targetFolderName = 'hdr_four_band_cases_20260915'
$targetImages = Join-Path $dataRoot $targetFolderName

if (-not (Test-Path -LiteralPath $sourceWeight)) { throw "找不到新權重：$sourceWeight" }
$images = @(Get-ChildItem -LiteralPath $SourceRoot -Recurse -File -Filter '*.jpg')
if ($images.Count -eq 0) { throw '資料集中沒有 JPG 圖片。' }

$records = foreach ($image in $images) {
    $relative = $image.FullName.Substring($SourceRoot.Length + 1)
    $segments = $relative -split '[\\/]'
    if ($segments.Count -lt 3 -or $segments[0] -notin @('train','val')) { throw "未知的資料路徑：$relative" }
    $split = $segments[0]
    $band = $segments[1]
    $stem = $image.BaseName
    $metadataPath = [System.IO.Path]::ChangeExtension($image.FullName, '.txt')
    if (-not (Test-Path -LiteralPath $metadataPath) -and $split -eq 'val') {
        $metadataPath = Join-Path $SourceRoot "train\$band\$stem.txt"
    }
    if (-not (Test-Path -LiteralPath $metadataPath)) { throw "找不到圖片說明：$relative" }
    $metadata = (Get-Content -LiteralPath $metadataPath -Raw).Trim()
    if ($metadata -match '(?i)(\d{1,3})\s*(?:%|percent)') {
        $wearPercent = [int]$Matches[1]
    } elseif ($metadata -match '(?i)fully worn') {
        $wearPercent = 100
    } else {
        throw "無法解析磨耗率：$metadataPath"
    }
    if ($wearPercent -lt 0 -or $wearPercent -gt 100) { throw "磨耗率超出範圍：$metadataPath" }

    $partsCut = 0
    if ($metadata -match '(?i)(\d+)\s*(?:parts|pieces|times)') {
        $partsCut = [int]$Matches[1]
    } elseif ($metadata -match '(?i)Ninety-five') {
        $partsCut = 95
    } elseif ($metadata -match '(?i)Two hundred') {
        $partsCut = 200
    } elseif ($metadata -match '(?i)Twelve') {
        $partsCut = 12
    }

    $safeBand = $band -replace '[^0-9-]', ''
    $targetName = "$split-$safeBand-$($image.Name)"
    [pscustomobject]@{
        id = ('HDR-{0:D3}-{1}-{2}' -f $wearPercent, $split, $stem)
        image = "data/$targetFolderName/$targetName"
        wear_rate = $wearPercent / 100.0
        wear_percent = $wearPercent
        wear_band = $band
        dataset_split = $split
        parts_cut = $partsCut
        source = '0914HDR分類_四區間'
        metadata = $metadata
        source_path = $image.FullName
        target_name = $targetName
    }
}

$duplicateIds = @($records | Group-Object id | Where-Object Count -gt 1)
if ($duplicateIds.Count) { throw "案例編號重複：$($duplicateIds.Name -join ', ')" }
if ($records.Count -ne $images.Count) { throw '案例數與圖片數不一致。' }

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $dataRoot "backups\hdr-update-$stamp"
New-Item -ItemType Directory -Path $backup -Force | Out-Null
Copy-Item -LiteralPath $casesPath -Destination (Join-Path $backup 'cases.json') -Force
Copy-Item -LiteralPath $targetWeight -Destination (Join-Path $backup 'keypoint-best.pt') -Force
New-Item -ItemType Directory -Path $targetImages -Force | Out-Null

foreach ($record in $records) {
    Copy-Item -LiteralPath $record.source_path -Destination (Join-Path $targetImages $record.target_name) -Force
    $record.PSObject.Properties.Remove('source_path')
    $record.PSObject.Properties.Remove('target_name')
}

$tempCases = "$casesPath.new"
[System.IO.File]::WriteAllText($tempCases, ($records | ConvertTo-Json -Depth 5), (New-Object System.Text.UTF8Encoding($false)))
Move-Item -LiteralPath $tempCases -Destination $casesPath -Force
Copy-Item -LiteralPath $sourceWeight -Destination $targetWeight -Force

$manifest = [pscustomobject]@{
    updated_at = (Get-Date).ToString('o')
    case_count = $records.Count
    by_band = @($records | Group-Object wear_band | Sort-Object Name | ForEach-Object { [pscustomobject]@{ band=$_.Name; count=$_.Count } })
    by_split = @($records | Group-Object dataset_split | Sort-Object Name | ForEach-Object { [pscustomobject]@{ split=$_.Name; count=$_.Count } })
    weight_sha256 = (Get-FileHash -LiteralPath $targetWeight -Algorithm SHA256).Hash
    backup = "data/backups/$(Split-Path $backup -Leaf)"
}
[System.IO.File]::WriteAllText((Join-Path $dataRoot 'hdr_dataset_manifest.json'), ($manifest | ConvertTo-Json -Depth 5), (New-Object System.Text.UTF8Encoding($false)))
$manifest | ConvertTo-Json -Depth 5
