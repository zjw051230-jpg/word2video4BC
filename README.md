# word2video4BC

面向 Codex 的多项目文字转视频生产工作区。仓库提供可移植安装器、空白项目结构、任务日志、不可变快照规则，以及完整的 Seedance 2.0 提示词技能。

## 安装

本工具的主要操作入口是 Codex。安装后直接告诉 Codex 要创建项目、整理素材、写提示词、生成、监控或拉回；Codex 会按技能和任务记录完成工作。只有安装扫描和 API Key 等涉密配置使用本机程序。

首次安装时双击 `VideoToolkitSetup.pyw`。安装器只负责扫描本机环境并安装缺失的视频技能；如果检测到配音工具的 Codex 技能或音频程序，视频工具不会重复安装、覆盖或修改它们。

若需要脚本方式，Windows PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& ".\install.ps1" -WorkspaceRoot "D:\视频生成" -ProjectName "项目1"
```

安装后，在 Codex 中说：

```text
我要创建项目，名字叫 项目1。请使用 manage-video-production 管理整个视频生产流程。
```

配置 Seedance API（仅涉密信息使用程序）：

安装完成后双击工作区中的 `Seedance API配置.pyw`，仅在窗口中填写 API Key。密钥配置完成后，回到 Codex 继续所有非涉密操作。

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

## Codex 主入口

首次进入每个项目时，Codex 会建立七个独立会话：任务理解与镜头规划、背景与关键帧、视频提示词、生成提交、监控、拉回、交付与复盘。显示名称统一为 `视频生成 | XXX`，并在项目隐藏 `.codex` 目录保存真实 thread ID、固定模型、0/1 状态和交接租约。

自动会话最高使用 `gpt-5.6-sol / medium`，大部分阶段使用 `gpt-5.6-terra / medium`；交付与复盘使用 `gpt-5.5 / medium`，由 CC Switch 精确映射到 `deepseek-v4-pro`。`sol/high` 只能由用户手动临时开启，完成后必须恢复合同模型和 `medium`。

可直接对 Codex 说：

```text
我要创建项目，名字叫 项目1。
```

```text
在项目1中整理这批素材，先生成提示词并停下来让我审核，不要提交付费任务。
```

```text
提交已审核的任务，拿到远程ID后停止，不要监控和拉回。
```

```text
监控项目1的全部任务，等全部成功或失败后统一拉回，并记录结果。
```

生产项目、成片、API 密钥、快照、历史任务日志和本机缓存均不发布。

详见 [首次安装与使用](docs/首次安装与使用.md) 和 [发布边界](docs/发布边界.md)。
