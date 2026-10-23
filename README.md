# HOOPLOG v7 修复说明

修复 Safari 中 `null is not an object (evaluating e.message)` 错误：异常对象可能为 null；Google OAuth 返回空响应时现在显示明确提示。保留 Excel A-E 列解析和按 A 列文件夹名匹配、两次 Wi-Fi 确认、缓存功能。

部署：覆盖 GitHub 仓库根目录的 index.html、sw.js、manifest.webmanifest，提交后刷新网页；不要清除 Safari 网站数据。

截图中的「53 个视频、54 行匹配记录」说明文件夹记录已经匹配，但**不代表 54 个视频都成功匹配**。重新同步后检查统计页和每个视频的动作备注。
