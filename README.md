# 视频生产工具

这是一套面向 Windows 的多项目视频生产工具，主要用于管理 Seedance 项目、素材、提示词、生成任务和交付记录。当前版本为 `2.2.0`。

工具目录和项目素材彼此分开：仓库只维护脚本、模板和工作流，实际项目、成片、密钥与本机任务记录不会提交到 Git。

## 安装

先安装 [media-production-env](https://github.com/zjw051230-jpg/media-production-env)，再运行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& ".\install.ps1" -WorkspaceRoot "D:\视频生成" -ProjectName "项目1"
```

安装器采用增量更新，只处理清单中声明的工具文件，不会整理或覆盖现有项目素材。

## 日常使用

安装完成后，可以在 Codex 中直接描述要做的事，例如：

```text
创建一个名为“项目1”的视频项目。
```

```text
整理项目1的素材并生成提示词，先停下来等我审核。
```

```text
提交已经审核的任务，记录远程任务 ID。
```

项目创建、提示词、提交、监控和交付分别保留记录，便于中途恢复和复盘。

## 工作区结构

```text
D:\视频生成\
├─ 视频本体\      # 工具、模板、全局 Skills 和运行日志
└─ 项目资源\      # 素材、生成结果、交付和快照
```

仓库中的主要内容：

- `New-VideoProject.ps1`：创建相互隔离的项目目录。
- `skills/`：项目管理、任务日志和 Seedance 工作流。
- `templates/`：新项目模板。
- `scripts/`：安装与校验脚本。

更多说明见 [首次安装与使用](docs/首次安装与使用.md) 和 [发布边界](docs/发布边界.md)。
