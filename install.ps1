[CmdletBinding()]
param(
  [string]$WorkspaceRoot = 'D:\视频生成',
  [string]$ProjectName = '',
  [string]$CodexHome = '',
  [switch]$Force
)

$ErrorActionPreference = 'Stop'
$packageRoot = $PSScriptRoot
$manifestPath = Join-Path $packageRoot 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw "安装包缺少 manifest.json。" }
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw '未找到 Python 启动器 py，请先安装 Python 3.10 或更高版本。' }

$WorkspaceRoot = [IO.Path]::GetFullPath($WorkspaceRoot)
if ([string]::IsNullOrWhiteSpace($CodexHome)) {
  $CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
}
$CodexHome = [IO.Path]::GetFullPath($CodexHome)

$workspaceDirs = @('1.projects','2.submission','3.skills\global','4.apis\seedance','5.summary\global','6.snapshot')
foreach ($dir in $workspaceDirs) { New-Item -ItemType Directory -Force -Path (Join-Path $WorkspaceRoot $dir) | Out-Null }

function Copy-VersionedDirectory {
  param([string]$Source, [string]$Target)
  if (Test-Path -LiteralPath $Target) {
    if (-not $Force) { throw "目标已存在：$Target。确认更新后使用 -Force。" }
    $backup = "$Target.backup.$(Get-Date -Format 'yyyyMMddHHmmss')"
    Move-Item -LiteralPath $Target -Destination $backup
  }
  Copy-Item -LiteralPath $Source -Destination $Target -Recurse
}

$workspaceSkillRoot = Join-Path $WorkspaceRoot '3.skills\global'
$codexSkillRoot = Join-Path $CodexHome 'skills'
New-Item -ItemType Directory -Force -Path $codexSkillRoot | Out-Null
$installedSkillRoots = @()
foreach ($skill in $manifest.skills) {
  $source = Join-Path (Join-Path $packageRoot 'skills') $skill
  if (-not (Test-Path -LiteralPath $source)) { throw "安装包缺少技能：$skill" }
  $workspaceTarget = Join-Path $workspaceSkillRoot $skill
  $codexTarget = Join-Path $codexSkillRoot $skill
  Copy-VersionedDirectory -Source $source -Target $workspaceTarget
  Copy-VersionedDirectory -Source $source -Target $codexTarget
  $installedSkillRoots += $workspaceTarget, $codexTarget
}

$textExtensions = @('.md','.py','.ps1','.json','.yaml','.yml','.txt')
foreach ($root in $installedSkillRoots) {
  foreach ($file in Get-ChildItem -LiteralPath $root -Recurse -File -Force) {
    if ($file.Extension -notin $textExtensions) { continue }
    $content = [IO.File]::ReadAllText($file.FullName)
    $updated = $content.Replace('D:\视频生成', $WorkspaceRoot)
    if ($updated -ne $content) {
      $withBom = $file.Extension -eq '.ps1'
      [IO.File]::WriteAllText($file.FullName, $updated, [Text.UTF8Encoding]::new($withBom))
    }
  }
}

Copy-Item -LiteralPath (Join-Path $packageRoot 'New-VideoProject.ps1') -Destination (Join-Path $WorkspaceRoot 'New-VideoProject.ps1') -Force
Copy-Item -LiteralPath (Join-Path $packageRoot 'Configure-SeedanceApi.ps1') -Destination (Join-Path $WorkspaceRoot 'Configure-SeedanceApi.ps1') -Force
Copy-Item -LiteralPath (Join-Path $packageRoot 'templates\api\seedance\provider.json') -Destination (Join-Path $WorkspaceRoot '4.apis\seedance\provider.json') -Force
Copy-Item -LiteralPath (Join-Path $packageRoot 'docs\Seedance-API操作规范.md') -Destination (Join-Path $WorkspaceRoot '4.apis\seedance\Seedance-API操作规范.md') -Force
foreach ($scriptName in @('New-VideoProject.ps1', 'Configure-SeedanceApi.ps1')) {
  $scriptPath = Join-Path $WorkspaceRoot $scriptName
  $content = [IO.File]::ReadAllText($scriptPath)
  [IO.File]::WriteAllText($scriptPath, $content.Replace('D:\视频生成', $WorkspaceRoot), [Text.UTF8Encoding]::new($true))
}

$globalLessons = Join-Path $WorkspaceRoot '5.summary\global\lessons.md'
if (-not (Test-Path -LiteralPath $globalLessons)) {
  [IO.File]::WriteAllText($globalLessons, "# Global production lessons`r`n", [Text.UTF8Encoding]::new($false))
}
$taskLog = Join-Path $WorkspaceRoot 'task-log.jsonl'
if (-not (Test-Path -LiteralPath $taskLog)) { [IO.File]::WriteAllText($taskLog, '', [Text.UTF8Encoding]::new($false)) }

if (-not [string]::IsNullOrWhiteSpace($ProjectName)) {
  & (Join-Path $WorkspaceRoot 'New-VideoProject.ps1') -WorkspaceRoot $WorkspaceRoot -ProjectName $ProjectName -Force:$Force
}

& py -3 -B -X utf8 (Join-Path $packageRoot 'scripts\validate_package.py') --package-root $packageRoot --workspace-root $WorkspaceRoot --codex-home $CodexHome
if ($LASTEXITCODE -ne 0) { throw "安装校验失败，退出码：$LASTEXITCODE" }

Write-Output "安装完成。工作区：$WorkspaceRoot"
Write-Output "Codex 技能目录：$codexSkillRoot"
if ($ProjectName) { Write-Output "初始项目：$ProjectName" }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { Write-Warning '未找到 ffmpeg；提示词与项目管理可用，但抽帧、转码和拼接功能需要另行安装 ffmpeg。' }
