[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Project,

    [Parameter(Mandatory = $true)]
    [string]$TaskId,

    [ValidatePattern('^\d{4}-\d{2}-\d{2}$')]
    [string]$TaskDate = (Get-Date -Format 'yyyy-MM-dd'),

    [Parameter(Mandatory = $true)]
    [string]$Summary,

    [ValidatePattern('^[a-zA-Z0-9-]+$')]
    [string]$Label = 'work',

    [string]$WorkspaceRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..\..'))
}

function Test-SafeName {
    param([Parameter(Mandatory = $true)][string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value) -or $Value -in '.', '..') {
        return $false
    }

    return $Value.IndexOfAny([System.IO.Path]::GetInvalidFileNameChars()) -lt 0
}

function Limit-TextElements {
    param(
        [Parameter(Mandatory = $true)][string]$Value,
        [Parameter(Mandatory = $true)][int]$Maximum
    )

    $indexes = [System.Globalization.StringInfo]::ParseCombiningCharacters($Value)
    if ($indexes.Count -le $Maximum) {
        return $Value
    }

    return $Value.Substring(0, $indexes[$Maximum])
}

$Project = $Project.Trim()
$TaskId = $TaskId.Trim()
$Summary = (Limit-TextElements -Value $Summary.Trim() -Maximum 10).TrimEnd('.', ' ')

foreach ($value in @($Project, $TaskId, $Summary)) {
    if (-not (Test-SafeName -Value $value)) {
        throw "Unsafe or empty path component: '$value'"
    }
}

$workspacePath = [System.IO.Path]::GetFullPath($WorkspaceRoot)
$resourceRoot = Join-Path $workspacePath '项目资源'
if (Test-Path -LiteralPath $resourceRoot -PathType Container) {
    $projectsRoot = [System.IO.Path]::GetFullPath((Join-Path $resourceRoot '1.projects'))
    $snapshotRoot = Join-Path $resourceRoot '6.snapshot'
}
else {
    # Compatibility fallback while an old workspace is awaiting migration.
    $projectsRoot = [System.IO.Path]::GetFullPath((Join-Path $workspacePath '1.projects'))
    $snapshotRoot = Join-Path $workspacePath '6.snapshot'
}
$projectPath = [System.IO.Path]::GetFullPath((Join-Path $projectsRoot $Project))
$projectsPrefix = $projectsRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar

if (-not $projectPath.StartsWith($projectsPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Resolved project path escaped the canonical projects root.'
}

if (-not (Test-Path -LiteralPath $projectPath -PathType Container)) {
    throw "Project directory does not exist: $projectPath"
}

$taskFolder = '{0}_{1}_{2}' -f $TaskDate, $TaskId, $Summary
$taskRoot = Join-Path (Join-Path $snapshotRoot $Project) $taskFolder
New-Item -ItemType Directory -Path $taskRoot -Force | Out-Null

$versions = Get-ChildItem -LiteralPath $taskRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^v(?<number>\d+)-' } |
    ForEach-Object { [int]$Matches.number }
$nextVersion = if ($versions) {
    [int](($versions | Measure-Object -Maximum).Maximum + 1)
}
else {
    [int]1
}
$versionName = 'v{0:D3}-{1}' -f $nextVersion, $Label
$finalPath = Join-Path $taskRoot $versionName

if (Test-Path -LiteralPath $finalPath) {
    throw "Snapshot already exists: $finalPath"
}

$tempPath = Join-Path $taskRoot ('.tmp-' + [guid]::NewGuid().ToString('N'))

try {
    $snapshotProjectPath = Join-Path $tempPath 'project'
    New-Item -ItemType Directory -Path $snapshotProjectPath -Force | Out-Null

    Get-ChildItem -Force -LiteralPath $projectPath | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $snapshotProjectPath -Recurse -Force
    }

    $manifest = [ordered]@{
        project = $Project
        task_id = $TaskId
        task_date = $TaskDate
        summary = $Summary
        version = $nextVersion
        label = $Label
        source = $projectPath
        created_at = (Get-Date).ToString('o')
    }
    $manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $tempPath '_snapshot.json') -Encoding utf8
    Move-Item -LiteralPath $tempPath -Destination $finalPath
}
catch {
    if (Test-Path -LiteralPath $tempPath) {
        Remove-Item -LiteralPath $tempPath -Recurse -Force
    }
    throw
}

Write-Output $finalPath
