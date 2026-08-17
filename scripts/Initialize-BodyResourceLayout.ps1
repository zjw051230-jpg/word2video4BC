[CmdletBinding()]
param(
  [string]$WorkspaceRoot = 'D:\视频生成',
  [switch]$MigrateLegacy
)

$ErrorActionPreference = 'Stop'
$WorkspaceRoot = [IO.Path]::GetFullPath($WorkspaceRoot)

$BodyRoot = Join-Path $WorkspaceRoot '视频本体'
$ResourceRoot = Join-Path $WorkspaceRoot '项目资源'
$BodyToolsRoot = Join-Path $BodyRoot '01_程序与工具'
$BodyGlobalSkills = Join-Path $BodyToolsRoot '3.skills\global'
$BodyIndexRoot = Join-Path $BodyRoot '02_任务索引'
$BodyLogRoot = Join-Path $BodyRoot '03_运行日志'
$BodyGlobalLessons = Join-Path $BodyLogRoot '全局复盘'
$BodyTemplatesRoot = Join-Path $BodyRoot '04_模板与规范'
$ResourceSkillsRoot = Join-Path $ResourceRoot '3.skills'
$ResourceSummaryRoot = Join-Path $ResourceRoot '5.summary'
$CacheRoot = Join-Path $ResourceRoot '00_本机缓存与测试'

function Test-EquivalentJunction {
  param([string]$Path, [string]$Target)
  if (-not (Test-Path -LiteralPath $Path)) { return $false }
  $item = Get-Item -LiteralPath $Path -Force
  if ([string]::IsNullOrWhiteSpace([string]$item.LinkType)) { return $false }
  foreach ($candidate in @($item.Target)) {
    if ([string]::IsNullOrWhiteSpace([string]$candidate)) { continue }
    $normalized = [string]$candidate -replace '^\\\?\?\\', ''
    if ([IO.Path]::GetFullPath($normalized).TrimEnd('\') -eq [IO.Path]::GetFullPath($Target).TrimEnd('\')) {
      return $true
    }
  }
  return $false
}

function Assert-PathParent {
  param([string]$Path)
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null
}

function Ensure-Junction {
  param([string]$Path, [string]$Target)
  if (Test-EquivalentJunction $Path $Target) {
    & attrib +h $Path /L | Out-Null
    return
  }
  if (Test-Path -LiteralPath $Path) { throw "兼容路径已被其他内容占用：$Path" }
  if (-not (Test-Path -LiteralPath $Target -PathType Container)) { throw "Junction 目标不存在：$Target" }
  Assert-PathParent $Path
  New-Item -ItemType Junction -Path $Path -Target $Target | Out-Null
  & attrib +h $Path /L | Out-Null
}

function Test-SameFileContent {
  param([string]$Left, [string]$Right)
  if (-not ((Test-Path -LiteralPath $Left -PathType Leaf) -and (Test-Path -LiteralPath $Right -PathType Leaf))) { return $false }
  $leftItem = Get-Item -LiteralPath $Left -Force
  $rightItem = Get-Item -LiteralPath $Right -Force
  if ($leftItem.Length -ne $rightItem.Length) { return $false }
  return (Get-FileHash -LiteralPath $Left -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $Right -Algorithm SHA256).Hash
}

function Ensure-HardLink {
  param([string]$Path, [string]$Target)
  if (Test-Path -LiteralPath $Path -PathType Leaf) {
    if (-not (Test-SameFileContent $Path $Target)) { throw "兼容文件与目标内容不同：$Path" }
    Remove-Item -LiteralPath $Path -Force
  }
  Assert-PathParent $Path
  New-Item -ItemType HardLink -Path $Path -Target $Target | Out-Null
  attrib +h $Path | Out-Null
}

function Move-LegacyDirectory {
  param([string]$Source, [string]$Target)
  if (Test-EquivalentJunction $Source $Target) { return }
  if (Test-Path -LiteralPath $Source) {
    $item = Get-Item -LiteralPath $Source -Force
    if ($item.LinkType) { throw "发现指向未知位置的链接，拒绝改写：$Source" }
    if (-not $MigrateLegacy) { throw "检测到旧工作区目录：$Source。请使用 -MigrateLegacy 显式迁移。" }
    if (Test-Path -LiteralPath $Target) { throw "目标目录已存在，拒绝合并：$Target" }
    Assert-PathParent $Target
    Move-Item -LiteralPath $Source -Destination $Target
  } elseif (-not (Test-Path -LiteralPath $Target)) {
    Assert-PathParent $Target
    New-Item -ItemType Directory -Force -Path $Target | Out-Null
  }
  Ensure-Junction $Source $Target
}

function Move-LegacyFile {
  param([string]$Source, [string]$Target, [switch]$CreateIfMissing)
  if (Test-Path -LiteralPath $Source -PathType Leaf) {
    if (Test-Path -LiteralPath $Target -PathType Leaf) {
      if (-not (Test-SameFileContent $Source $Target)) { throw "目标文件已存在且内容不同，拒绝覆盖：$Target" }
    } else {
      if (-not $MigrateLegacy) { throw "检测到旧工作区文件：$Source。请使用 -MigrateLegacy 显式迁移。" }
      Assert-PathParent $Target
      Move-Item -LiteralPath $Source -Destination $Target
    }
  }
  if (-not (Test-Path -LiteralPath $Target -PathType Leaf) -and $CreateIfMissing) {
    Assert-PathParent $Target
    New-Item -ItemType File -Path $Target | Out-Null
  }
  if (Test-Path -LiteralPath $Target -PathType Leaf) { Ensure-HardLink $Source $Target }
}

function Move-SplitDirectory {
  param([string]$Source, [string]$Target)
  Move-LegacyDirectory -Source $Source -Target $Target
}

New-Item -ItemType Directory -Force -Path `
  $BodyRoot, $BodyToolsRoot, $BodyIndexRoot, $BodyLogRoot, $BodyTemplatesRoot, `
  $ResourceRoot, $ResourceSkillsRoot, $ResourceSummaryRoot, $CacheRoot | Out-Null

# Ordinary resource roots: real contents move once; legacy paths become hidden Junctions.
foreach ($mapping in @(
  @{ name = '1.projects'; target = (Join-Path $ResourceRoot '1.projects') },
  @{ name = '2.submission'; target = (Join-Path $ResourceRoot '2.submission') },
  @{ name = '4.apis'; target = (Join-Path $ResourceRoot '4.apis') },
  @{ name = '6.snapshot'; target = (Join-Path $ResourceRoot '6.snapshot') },
  @{ name = 'tmp'; target = (Join-Path $CacheRoot 'tmp') },
  @{ name = '.word2video4BC'; target = (Join-Path $BodyToolsRoot '.word2video4BC') }
)) {
  Move-LegacyDirectory -Source (Join-Path $WorkspaceRoot $mapping.name) -Target $mapping.target
}
New-Item -ItemType Directory -Force -Path (Join-Path $ResourceRoot '4.apis\seedance') | Out-Null

# Global skills are reusable tool code; project-specific skills remain with their project resources.
$legacySkills = Join-Path $WorkspaceRoot '3.skills'
if (-not (Test-Path -LiteralPath $legacySkills)) {
  New-Item -ItemType Directory -Force -Path $legacySkills | Out-Null
} elseif (-not (Test-EquivalentJunction $legacySkills $ResourceSkillsRoot)) {
  $skillRootItem = Get-Item -LiteralPath $legacySkills -Force
  if ($skillRootItem.LinkType) { throw "技能兼容根目录指向未知位置：$legacySkills" }
  $legacyGlobal = Join-Path $legacySkills 'global'
  Move-SplitDirectory -Source $legacyGlobal -Target $BodyGlobalSkills
  foreach ($item in @(Get-ChildItem -LiteralPath $legacySkills -Force -Directory)) {
    if ($item.Name -eq 'global' -or $item.LinkType) { continue }
    Move-SplitDirectory -Source $item.FullName -Target (Join-Path $ResourceSkillsRoot $item.Name)
  }
}
if (-not (Test-Path -LiteralPath $BodyGlobalSkills)) { New-Item -ItemType Directory -Force -Path $BodyGlobalSkills | Out-Null }
Ensure-Junction -Path (Join-Path $legacySkills 'global') -Target $BodyGlobalSkills
foreach ($item in @(Get-ChildItem -LiteralPath $ResourceSkillsRoot -Force -Directory)) {
  Ensure-Junction -Path (Join-Path $legacySkills $item.Name) -Target $item.FullName
}
attrib +h $legacySkills | Out-Null

# Global lessons are body knowledge; per-project lessons are resource records.
$legacySummary = Join-Path $WorkspaceRoot '5.summary'
if (-not (Test-Path -LiteralPath $legacySummary)) {
  New-Item -ItemType Directory -Force -Path $legacySummary | Out-Null
} else {
  $summaryRootItem = Get-Item -LiteralPath $legacySummary -Force
  if ($summaryRootItem.LinkType) { throw "复盘兼容根目录指向未知位置：$legacySummary" }
  Move-SplitDirectory -Source (Join-Path $legacySummary 'global') -Target $BodyGlobalLessons
  foreach ($item in @(Get-ChildItem -LiteralPath $legacySummary -Force -Directory)) {
    if ($item.Name -eq 'global' -or $item.LinkType) { continue }
    Move-SplitDirectory -Source $item.FullName -Target (Join-Path $ResourceSummaryRoot $item.Name)
  }
}
if (-not (Test-Path -LiteralPath $BodyGlobalLessons)) { New-Item -ItemType Directory -Force -Path $BodyGlobalLessons | Out-Null }
Ensure-Junction -Path (Join-Path $legacySummary 'global') -Target $BodyGlobalLessons
foreach ($item in @(Get-ChildItem -LiteralPath $ResourceSummaryRoot -Force -Directory)) {
  Ensure-Junction -Path (Join-Path $legacySummary $item.Name) -Target $item.FullName
}
attrib +h $legacySummary | Out-Null

# Operational log and the project-creation entry point belong to the tool body.
Move-LegacyFile -Source (Join-Path $WorkspaceRoot 'task-log.jsonl') -Target (Join-Path $BodyLogRoot 'task-log.jsonl') -CreateIfMissing
Move-LegacyFile -Source (Join-Path $WorkspaceRoot 'New-VideoProject.ps1') -Target (Join-Path $BodyToolsRoot 'New-VideoProject.ps1')

$rootTestFiles = @(
  'image-test.png',
  'seedance-test-i2v-response.json',
  'seedance-test-i2v-status.json',
  'seedance-test-i2v-v01.mp4',
  'seedance-test-response.json',
  'seedance-test-status.json',
  'seedance-test-v01.mp4'
)
$rootTestDir = Join-Path $CacheRoot '根目录测试'
foreach ($name in $rootTestFiles) {
  Move-LegacyFile -Source (Join-Path $WorkspaceRoot $name) -Target (Join-Path $rootTestDir $name)
}

$record = [ordered]@{
  schema_version = 2
  workspace_root = $WorkspaceRoot
  body_root = $BodyRoot
  resource_root = $ResourceRoot
  canonical_paths = [ordered]@{
    global_skills = $BodyGlobalSkills
    task_log = (Join-Path $BodyLogRoot 'task-log.jsonl')
    global_lessons = $BodyGlobalLessons
    projects = (Join-Path $ResourceRoot '1.projects')
    submissions = (Join-Path $ResourceRoot '2.submission')
    project_skills = $ResourceSkillsRoot
    api_configuration = (Join-Path $ResourceRoot '4.apis')
    project_summaries = $ResourceSummaryRoot
    snapshots = (Join-Path $ResourceRoot '6.snapshot')
    cache = $CacheRoot
  }
  legacy_compatibility = @('1.projects','2.submission','3.skills','4.apis','5.summary','6.snapshot','tmp','.word2video4BC','task-log.jsonl','New-VideoProject.ps1')
  migrated_legacy = [bool]$MigrateLegacy
  updated_at = (Get-Date).ToString('o')
}
$recordPath = Join-Path $BodyIndexRoot '本体资源分层.json'
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $recordPath -Encoding UTF8
Write-Output "BODY_ROOT=$BodyRoot"
Write-Output "RESOURCE_ROOT=$ResourceRoot"
