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
Write-Output "TEST PASSED: $TestRoot"
