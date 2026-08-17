[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$TestRoot
)

$ErrorActionPreference = 'Stop'
$TestRoot = [IO.Path]::GetFullPath($TestRoot)
$workspace = Join-Path $TestRoot '工作区'
$codexHome = Join-Path $TestRoot 'codex-home'
$packageRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))

if (Test-Path -LiteralPath $TestRoot) {
  $allowedParent = [IO.Path]::GetFullPath('D:\视频工具总结\test')
  $prefix = $allowedParent.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
  if (-not $TestRoot.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "拒绝清理测试目录之外的路径：$TestRoot"
  }
  Remove-Item -LiteralPath $TestRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $TestRoot | Out-Null

& (Join-Path $packageRoot 'install.ps1') -WorkspaceRoot $workspace -CodexHome $codexHome -ProjectName '测试项目'
if ($LASTEXITCODE -ne 0) { throw "安装器返回非零退出码：$LASTEXITCODE" }

& py -3 -B -X utf8 (Join-Path $packageRoot 'scripts\validate_package.py') `
  --package-root $packageRoot --workspace-root $workspace --codex-home $codexHome
if ($LASTEXITCODE -ne 0) { throw "安装后校验失败：$LASTEXITCODE" }

$logger = Join-Path $codexHome 'skills\maintain-task-log\scripts\task_log.py'
$logOutput = & py -3 -B -X utf8 $logger read --limit 1
if ($LASTEXITCODE -ne 0 -or (($logOutput -join "`n").Trim() -ne '[]')) {
  throw '新工作区任务日志不是空日志。'
}
& py -3 -B -X utf8 $logger append --task-id 'T20260817-000001' --phase '开始' --project '测试项目' --summary '安装验证' --did '验证本体任务日志写入。'
if ($LASTEXITCODE -ne 0) { throw '本体任务日志追加失败。' }
if (-not ((Get-Content -LiteralPath (Join-Path $workspace '视频本体\03_运行日志\task-log.jsonl') -Raw -Encoding UTF8) -match 'T20260817-000001')) {
  throw '本体任务日志未写入。'
}

$bodyRoot = Join-Path $workspace '视频本体'
$resourceRoot = Join-Path $workspace '项目资源'
foreach ($required in @(
  '01_程序与工具\3.skills\global', '02_任务索引', '03_运行日志\task-log.jsonl', '04_模板与规范'
)) {
  if (-not (Test-Path -LiteralPath (Join-Path $bodyRoot $required))) { throw "视频本体缺少：$required" }
}
foreach ($required in @('1.projects','2.submission','3.skills','4.apis\seedance','5.summary','6.snapshot','00_本机缓存与测试')) {
  if (-not (Test-Path -LiteralPath (Join-Path $resourceRoot $required))) { throw "项目资源缺少：$required" }
}
foreach ($required in @('1.projects','2.submission','3.skills\global','4.apis','5.summary\global','6.snapshot','task-log.jsonl','New-VideoProject.ps1')) {
  if (-not (Test-Path -LiteralPath (Join-Path $workspace $required))) { throw "兼容路径缺少：$required" }
}

$project = Join-Path $workspace '1.projects\测试项目'
foreach ($required in @('project.json','0.背景参考','4.rawtask','5.提示词包','6.生成结果','.codex\03_codexchat对应表.json')) {
  if (-not (Test-Path -LiteralPath (Join-Path $project $required))) { throw "测试项目缺少：$required" }
}
$chatTable = Get-Content -LiteralPath (Join-Path $project '.codex\03_codexchat对应表.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$chatProperties = @($chatTable.chats.PSObject.Properties)
if ($chatProperties.Count -ne 7) { throw "视频Chat数量错误：$($chatProperties.Count)" }
if (@($chatProperties | Where-Object { $_.Value.reasoning_effort -eq 'high' }).Count -ne 0) { throw '自动Chat合同不得包含high。' }
$delivery = $chatTable.chats.'视频生成 | 交付与复盘'
if ($delivery.model -ne 'gpt-5.5' -or $delivery.reasoning_effort -ne 'medium') { throw '交付与复盘模型合同错误。' }
$owner = $chatTable.chats.'视频生成 | 任务理解与镜头规划'
if ($owner.model -ne 'gpt-5.6-sol' -or $owner.reasoning_effort -ne 'medium') { throw '入口Chat模型合同错误。' }
$snapshotScript = Join-Path $workspace '视频本体\01_程序与工具\3.skills\global\manage-video-production\scripts\snapshot-project.ps1'
$snapshotPath = & $snapshotScript -WorkspaceRoot $workspace -Project '测试项目' -TaskId 'T20260817-000001' -TaskDate '2026-08-17' -Summary '安装验证' -Label 'before'
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $snapshotPath)) { throw '规范快照创建失败。' }
if (-not $snapshotPath.StartsWith((Join-Path $workspace '项目资源\6.snapshot'), [StringComparison]::OrdinalIgnoreCase)) {
  throw "快照未写入项目资源：$snapshotPath"
}
Write-Output "TEST PASSED: $TestRoot"
