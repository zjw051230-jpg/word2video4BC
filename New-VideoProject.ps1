[CmdletBinding()]
param(
  [string]$WorkspaceRoot = 'D:\视频生成',
  [Parameter(Mandatory = $true)]
  [string]$ProjectName,
  [switch]$Force
)

$ErrorActionPreference = 'Stop'
$WorkspaceRoot = [IO.Path]::GetFullPath($WorkspaceRoot)
$ProjectName = $ProjectName.Trim()
if ([string]::IsNullOrWhiteSpace($ProjectName) -or $ProjectName -in '.', '..' -or
    $ProjectName.IndexOfAny([IO.Path]::GetInvalidFileNameChars()) -ge 0) {
  throw "项目名为空或包含非法字符。"
}

$projectsRoot = [IO.Path]::GetFullPath((Join-Path $WorkspaceRoot '1.projects'))
$projectRoot = [IO.Path]::GetFullPath((Join-Path $projectsRoot $ProjectName))
$prefix = $projectsRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $projectRoot.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
  throw '项目路径越过了 1.projects。'
}
if ((Test-Path -LiteralPath $projectRoot) -and -not $Force) {
  throw "项目已存在：$projectRoot"
}

$dirs = @(
  '0.背景参考', '1.动作参考', '2.人物三视图', '3.文本资料',
  '4.rawtask', '5.提示词包', '6.生成结果', 'data'
)
New-Item -ItemType Directory -Force -Path $projectRoot | Out-Null
foreach ($dir in $dirs) { New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot $dir) | Out-Null }
New-Item -ItemType Directory -Force -Path `
  (Join-Path $WorkspaceRoot "2.submission\$ProjectName"), `
  (Join-Path $WorkspaceRoot "3.skills\$ProjectName"), `
  (Join-Path $WorkspaceRoot "5.summary\$ProjectName"), `
  (Join-Path $WorkspaceRoot "6.snapshot\$ProjectName") | Out-Null

$lessons = Join-Path $WorkspaceRoot "5.summary\$ProjectName\lessons.md"
if (-not (Test-Path -LiteralPath $lessons)) {
  [IO.File]::WriteAllText($lessons, "# $ProjectName 项目复盘`r`n", [Text.UTF8Encoding]::new($false))
}

$metadata = [ordered]@{
  schema_version = 1
  project_name = $ProjectName
  project_root = $projectRoot
  created_at = (Get-Date).ToString('o')
}
$json = $metadata | ConvertTo-Json -Depth 5
[IO.File]::WriteAllText((Join-Path $projectRoot 'project.json'), $json + "`r`n", [Text.UTF8Encoding]::new($false))
$readme = @"
# $ProjectName

这是项目的当前工作版本。素材按类型放入 0-3 目录，原始任务放入 4.rawtask，审核后的提示词放入 5.提示词包，生成结果放入 6.生成结果。
"@
[IO.File]::WriteAllText((Join-Path $projectRoot 'README.md'), $readme, [Text.UTF8Encoding]::new($false))
$chatInitializer = Join-Path $WorkspaceRoot '3.skills\global\manage-video-production\scripts\init_video_chat_workflow.py'
if (Test-Path -LiteralPath $chatInitializer) {
  & py -3 -B -X utf8 $chatInitializer --project-root $projectRoot
  if ($LASTEXITCODE -ne 0) { throw "视频多Chat工作流初始化失败：$LASTEXITCODE" }
}
Write-Output $projectRoot
