[CmdletBinding()]
param(
    [string]$MaterialRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) 'materials')
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$resolvedMaterialRoot = (Resolve-Path -LiteralPath $MaterialRoot).Path
$files = Get-ChildItem -LiteralPath $resolvedMaterialRoot -Recurse -File | Sort-Object FullName
$entries = foreach ($file in $files) {
    [ordered]@{
        path = $file.FullName.Substring($resolvedMaterialRoot.Length).TrimStart('\')
        bytes = $file.Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
    }
}
$totalBytes = [long](($files | Measure-Object -Property Length -Sum).Sum)
$manifest = [ordered]@{
    task_id = 'T20260812-144226'
    package = 'ol3d_minigame_ads_15versions'
    generated_at = (Get-Date).ToString('o')
    material_root = $resolvedMaterialRoot
    file_count = @($entries).Count
    total_bytes = $totalBytes
    files = @($entries)
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $repoRoot 'MATERIALS_MANIFEST.json') -Encoding utf8
Write-Output "Wrote MATERIALS_MANIFEST.json for $($manifest.file_count) files."
