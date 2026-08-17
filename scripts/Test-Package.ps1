[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

foreach ($name in @('README.md', 'VERSION.md', 'MATERIALS_MANIFEST.json')) {
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot $name))) {
        throw "Missing required package file: $name"
    }
}

$summaryPaths = @(Get-ChildItem -LiteralPath $repoRoot -Recurse -File -Filter 'rough_cut_summary.json')
if ($summaryPaths.Count -lt 1) { throw 'Missing rough_cut_summary.json' }
$summaryPath = $summaryPaths[0].FullName

$planningFiles = @(Get-ChildItem -LiteralPath $repoRoot -Recurse -File -Filter '*_production_plan.json')
if ($planningFiles.Count -ne 15) { throw "Expected 15 production plans, got $($planningFiles.Count)" }

$markdownFiles = @(Get-ChildItem -LiteralPath $repoRoot -Recurse -File -Filter '*.md')
if ($markdownFiles.Count -lt 20) { throw "Expected collaboration and planning markdown, got $($markdownFiles.Count) files" }

$summary = Get-Content -Raw -LiteralPath $summaryPath | ConvertFrom-Json
$versions = @($summary.versions)
if ($versions.Count -ne 15) { throw "Expected 15 rough-cut versions, got $($versions.Count)" }
foreach ($version in $versions) {
    if ($version.technical.strict_order_ok -ne $true -or $version.technical.all_inputs_in_own_original -ne $true) {
        throw "Order/ownership check failed for $($version.version_id)"
    }
}

Write-Output 'Package metadata check passed: 15 isolated rough-cut versions.'
