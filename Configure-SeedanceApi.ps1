[CmdletBinding()]
param(
  [string]$WorkspaceRoot = 'D:\视频生成',
  [string]$BaseUrl = 'https://chat.q1.com/v1',
  [string]$Model = 'doubao-seedance-2.0'
)

$ErrorActionPreference = 'Stop'
$WorkspaceRoot = [IO.Path]::GetFullPath($WorkspaceRoot)
$target = Join-Path $WorkspaceRoot '4.apis\seedance'
New-Item -ItemType Directory -Force -Path $target | Out-Null
$secure = Read-Host '请输入 Seedance API Key（输入内容不会显示）' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  if ([string]::IsNullOrWhiteSpace($apiKey)) { throw 'API Key 不能为空。' }
  $credentials = [ordered]@{
    api_key = $apiKey
    authorization_header = 'Authorization'
    authorization_scheme = 'Bearer'
  }
  $config = [ordered]@{ api_key = $apiKey; base_url = $BaseUrl; model = $Model }
  [IO.File]::WriteAllText((Join-Path $target 'credentials.json'), ($credentials | ConvertTo-Json) + "`r`n", [Text.UTF8Encoding]::new($false))
  [IO.File]::WriteAllText((Join-Path $target 'doubao_api_config.json'), ($config | ConvertTo-Json) + "`r`n", [Text.UTF8Encoding]::new($false))
}
finally {
  if ($ptr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
  $apiKey = $null
}
Write-Output "Seedance API 配置已写入：$target"

