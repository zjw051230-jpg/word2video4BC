[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$MaterialRoot
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$resolvedMaterialRoot = (Resolve-Path -LiteralPath $MaterialRoot).Path
$linkPath = Join-Path $repoRoot 'materials'

if (-not (Test-Path -LiteralPath (Join-Path $resolvedMaterialRoot '01_生成结果'))) {
    throw "Material package is missing 01_生成结果: $resolvedMaterialRoot"
}
if (-not (Test-Path -LiteralPath (Join-Path $resolvedMaterialRoot '02_秋季OL3D权威素材'))) {
    throw "Material package is missing 02_秋季OL3D权威素材: $resolvedMaterialRoot"
}
if (Test-Path -LiteralPath $linkPath) {
    $item = Get-Item -LiteralPath $linkPath -Force
    if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "Refusing to replace a normal directory: $linkPath"
    }
    Remove-Item -LiteralPath $linkPath -Force
}

New-Item -ItemType Junction -Path $linkPath -Target $resolvedMaterialRoot | Out-Null
Write-Output "Connected local material package: $linkPath -> $resolvedMaterialRoot"
