# 执行工具快照

本目录保存本批次实际使用过的无密钥 Python 工具快照，用于追溯与代码审查：

- `ol3d_minigame_ads_15versions_media.py`：素材上传、绑定审计与提交底层逻辑。
- `ol3d_minigame_ads_15versions_submit.py`：165 条提交与 V010 修复绑定门禁。
- `ol3d_minigame_ads_15versions_poll.py`：只查询既有远端 ID 的轮询逻辑。
- `ol3d_minigame_ads_15versions_pull_qc.py`：拉回、ffprobe、五帧及连续性质量检查。

这些文件没有 API 密钥，但依赖独立的本地 API 配置、已验证的服务端端点以及本批次的原始工作区布局。因此它们是“本次执行的可审计快照”，不是跨机器直接运行的安装器。

继续生产时应先按项目工作流配置本机 API，再基于本仓库的版本隔离、真实回执、素材哈希和审查门禁创建新的执行轮次。不得把本目录中的历史脚本、真实远端 ID、上传 URL 或响应记录当作可以跨版本复制的素材来源。
