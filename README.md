# word2video4BC

面向 Codex 的多项目文字转视频生产工作区。仓库提供可移植安装器、空白项目结构、任务日志、不可变快照规则，以及完整的 Seedance 2.0 提示词技能。

## 安装

Windows PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& ".\install.ps1" -WorkspaceRoot "D:\视频生成" -ProjectName "项目1"
```

安装后，在 Codex 中说：

```text
我要创建项目，名字叫 项目1。请使用 manage-video-production 管理整个视频生产流程。
```

配置 Seedance API：

```powershell
& "D:\视频生成\Configure-SeedanceApi.ps1"
```

密钥只写入本机工作区 `4.apis`，不会进入本仓库。

## 包含内容

- `manage-video-production`：项目、任务、版本、提交和复盘规范。
- `maintain-task-log`：全局追加式任务日志。
- `seedance-20`：Seedance 2.0 提示词、镜头、动作、音频、连续性和排错技能集。
- `New-VideoProject.ps1`：创建多个相互隔离的项目。
- `validate_package.py`：检查安装包结构、路径替换和敏感数据。

生产项目、成片、API 密钥、快照、历史任务日志和本机缓存均不发布。

详见 [首次安装与使用](docs/首次安装与使用.md) 和 [发布边界](docs/发布边界.md)。

