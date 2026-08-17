[CmdletBinding()]
param(
  [string]$WorkspaceRoot = 'D:\视频生成',
  [string]$ProjectName = '',
  [string]$CodexHome = '',
  [string]$Env4BCRoot = '',
  [string]$Env4BCPackage = '',
  [switch]$Offline,
  [switch]$UpdateOnly,
  [switch]$Force
)

$ErrorActionPreference = 'Stop'
$packageRoot = $PSScriptRoot
$manifestPath = Join-Path $packageRoot 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw "安装包缺少 manifest.json。" }
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
& (Join-Path $packageRoot 'scripts\Resolve-Env4BC.ps1') -InstallRoot $Env4BCRoot -LocalPackage $Env4BCPackage -Offline:$Offline
if ($LASTEXITCODE -ne 0) { throw 'env4BC 环境资源钩子失败。' }
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'env4BC 未能提供 Python，已停止，请联系维护人员处理。' }

$WorkspaceRoot = [IO.Path]::GetFullPath($WorkspaceRoot)
if ([string]::IsNullOrWhiteSpace($CodexHome)) {
  $CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
}
$CodexHome = [IO.Path]::GetFullPath($CodexHome)

$layoutScript = Join-Path $packageRoot 'scripts\Initialize-BodyResourceLayout.ps1'
if (-not (Test-Path -LiteralPath $layoutScript -PathType Leaf)) { throw "安装包缺少本体/资源分层器：$layoutScript" }
& $layoutScript -WorkspaceRoot $WorkspaceRoot -MigrateLegacy
if ($LASTEXITCODE -ne 0) { throw '本体/资源分层初始化失败。' }

$bodyRoot = Join-Path $WorkspaceRoot '视频本体'
$bodyToolsRoot = Join-Path $bodyRoot '01_程序与工具'
$workspaceSkillRoot = Join-Path $bodyToolsRoot '3.skills\global'
$bodyLogRoot = Join-Path $bodyRoot '03_运行日志'
$bodyGlobalLessons = Join-Path $bodyLogRoot '全局复盘\lessons.md'

function Copy-VersionedDirectory {
  param([string]$Source, [string]$Target)
  if (Test-Path -LiteralPath $Target) {
    if (-not $Force) { throw "目标已存在：$Target。确认更新后使用 -Force。" }
    $backup = "$Target.backup.$(Get-Date -Format 'yyyyMMddHHmmss')"
    Move-Item -LiteralPath $Target -Destination $backup
  }
  Copy-Item -LiteralPath $Source -Destination $Target -Recurse
}

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

$newProjectTarget = Join-Path $bodyToolsRoot 'New-VideoProject.ps1'
Copy-Item -LiteralPath (Join-Path $packageRoot 'New-VideoProject.ps1') -Destination $newProjectTarget -Force
$newProjectContent = [IO.File]::ReadAllText($newProjectTarget)
[IO.File]::WriteAllText($newProjectTarget, $newProjectContent.Replace('D:\视频生成', $WorkspaceRoot), [Text.UTF8Encoding]::new($true))
$legacyNewProject = Join-Path $WorkspaceRoot 'New-VideoProject.ps1'
if (Test-Path -LiteralPath $legacyNewProject) { Remove-Item -LiteralPath $legacyNewProject -Force }
New-Item -ItemType HardLink -Path $legacyNewProject -Target $newProjectTarget | Out-Null
attrib +h $legacyNewProject | Out-Null

$globalLessons = $bodyGlobalLessons
if (-not $UpdateOnly -and -not (Test-Path -LiteralPath $globalLessons)) {
  [IO.File]::WriteAllText($globalLessons, "# Global production lessons`r`n", [Text.UTF8Encoding]::new($false))
}
$taskLog = Join-Path $bodyLogRoot 'task-log.jsonl'
if (-not $UpdateOnly -and -not (Test-Path -LiteralPath $taskLog)) { [IO.File]::WriteAllText($taskLog, '', [Text.UTF8Encoding]::new($false)) }

if (-not $UpdateOnly -and -not [string]::IsNullOrWhiteSpace($ProjectName)) {
  & (Join-Path $WorkspaceRoot 'New-VideoProject.ps1') -WorkspaceRoot $WorkspaceRoot -ProjectName $ProjectName -Force:$Force
}

& py -3 -B -X utf8 (Join-Path $packageRoot 'scripts\validate_package.py') --package-root $packageRoot --workspace-root $WorkspaceRoot --codex-home $CodexHome
if ($LASTEXITCODE -ne 0) { throw "安装校验失败，退出码：$LASTEXITCODE" }

Write-Output "安装完成。工作区：$WorkspaceRoot"
Write-Output "Codex 技能目录：$codexSkillRoot"
if ($ProjectName) { Write-Output "初始项目：$ProjectName" }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { Write-Warning '未找到 ffmpeg；提示词与项目管理可用，但抽帧、转码和拼接功能需要另行安装 ffmpeg。' }

$toolStateRoot = Join-Path $WorkspaceRoot '.word2video4BC'
New-Item -ItemType Directory -Force -Path $toolStateRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $packageRoot 'scripts\Update-Toolkit.ps1') -Destination (Join-Path $toolStateRoot 'Update-Toolkit.ps1') -Force
[ordered]@{schema_version=3;repository='https://github.com/zjw051230-jpg/word2video4BC';main_branch='main';checkout_root=$packageRoot;update_transport='git-pull';installed_version=$manifest.version;update_command="powershell -ExecutionPolicy Bypass -File `"$toolStateRoot\Update-Toolkit.ps1`" -WorkspaceRoot `"$WorkspaceRoot`"";managed_scope=@('视频本体\01_程序与工具\3.skills\global','Codex skills','视频本体\01_程序与工具\New-VideoProject.ps1');protected_scope=@('项目资源','项目与素材','生成结果','交付','快照','私有 API','缓存','项目复盘');legacy_compatibility=@('1.projects','2.submission','3.skills','4.apis','5.summary','6.snapshot','tmp','task-log.jsonl','New-VideoProject.ps1');updated_at=(Get-Date).ToString('o')} | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $toolStateRoot 'update-source.json')
attrib +h $toolStateRoot | Out-Null
