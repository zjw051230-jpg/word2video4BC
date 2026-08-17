[CmdletBinding()]
param(
  [string]$WorkspaceRoot = 'D:\视频生成',
  [string]$CodexHome = '',
  [switch]$Offline
)

$ErrorActionPreference = 'Stop'
$expectedRepository = 'https://github.com/zjw051230-jpg/word2video4BC'
if ($Offline) { throw '离线模式不能执行 git pull；请联网后由 Codex 更新工具。' }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw '未找到 Git，无法从 main 直接更新工具。' }

$statePath = Join-Path $PSScriptRoot 'update-source.json'
if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) { throw "缺少更新来源记录：$statePath" }
try { $state = Get-Content -Raw -Encoding UTF8 -LiteralPath $statePath | ConvertFrom-Json } catch { throw '更新来源记录无法解析。' }

if ([string]$state.repository -ne $expectedRepository) { throw '更新来源不是批准的官方仓库，已停止。' }
$checkoutRoot = [string]$state.checkout_root
if ([string]::IsNullOrWhiteSpace($checkoutRoot) -or -not (Test-Path -LiteralPath (Join-Path $checkoutRoot '.git'))) {
  throw '未找到原始 Git 工作副本；请重新 clone 官方仓库后执行 install.ps1。'
}

$branch = (& git -C $checkoutRoot branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or $branch -ne 'main') { throw '工具工作副本必须位于 main 分支，已停止。' }
$origin = (& git -C $checkoutRoot remote get-url origin).Trim().TrimEnd('/')
if ($LASTEXITCODE -ne 0 -or $origin -notin @($expectedRepository, "$expectedRepository.git")) {
  throw '工具工作副本的 origin 不是批准的官方仓库，已停止。'
}
if ((& git -C $checkoutRoot status --porcelain)) { throw '工具工作副本存在未提交改动；请先处理后再更新。' }

& git -C $checkoutRoot pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { throw 'git pull --ff-only 失败；未修改工作区或项目数据。' }

$installer = Join-Path $checkoutRoot 'install.ps1'
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) { throw '更新后的工具工作副本缺少 install.ps1。' }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer -WorkspaceRoot $WorkspaceRoot -CodexHome $CodexHome -UpdateOnly -Force
if ($LASTEXITCODE -ne 0) { throw '工具安装更新失败；项目资源未作为更新目标。' }

$head = (& git -C $checkoutRoot rev-parse --short HEAD).Trim()
Write-Output "UPDATED:main@$head"
