# HOOPLOG v18 —— 「冒险」摄影姿势库 + Google Drive 自动上传

## 升级内容

在 HOOPLOG v17「动作名修正版」基础上增加底部 **「冒险」** 入口（六个菜单，原篮球功能保留）。

- **姿势图库**：从手机上传姿势模板原图，记录模板名称、拍摄技术、通用备注。
- **顾客**：新增顾客，各有独立的拍摄记录与约拍计划。
- **下次约拍**：为每位顾客累积选中的模板，可移除或重新加入。已拍后可标记满意/重拍。
- **模板对照**：左边模板、右边顾客实拍；同一顾客与模板允许反复上传、切换历次实拍，记录评价与下次重拍/继续拍。
- **云端同步**：Google Drive API 上传未压缩的原始选取文件 + 数据索引 JSON，上传状态明确区分「已同步 / 待同步」，失败保留本机文件以重试。

## 发布到 GitHub Pages

日常开发流程改为：**手机提出需求 → 获取最新代码 → 独立分支修改和测试 → PR 展示结果 → 用户确认 → 合并 main → 自动检查并部署 Pages**。不需要下载 ZIP 或手动覆盖文件。开发约定见 [AGENTS.md](AGENTS.md)。

`.github/workflows/pages.yml` 在 PR 中运行 Chromium 和 WebKit 功能测试，生成 `hooplog-preview-<commit>` 构建供审查；PR 不会发布正式站。切换 Pages 发布源后，该工作流仅在合并到 `main` 且两种浏览器检查均成功时部署。工作流完成部署后还会核对 `version.json` 的提交号和静态资源，避免仅凭页面标题判断版本。

首次启用此流程时，需要在 GitHub 仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。应在用户批准的迁移时机完成设置，不要为了检查 PR 擅自修改线上发布源。只合并 YAML、仍保留原来的分支发布源时，旧 Pages 流程可能绕过测试立即部署，并与新流程竞争，因此不能声称发布门禁已生效。建议同时在分支规则中要求 PR 和两项 `Check` 成功，防止绕过确认直接推送 `main`。

预览构建可从 PR 的 Actions 运行页面下载，用静态服务器查看；它不是公开预览网址。生成的测试截图单独保存为 `hooplog-screenshots-<browser>-<commit>` 构件，只含合成测试资料，不放入正式站目录。当前没有配置独立的在线 PR 预览托管，手机审查可先查看截图和测试报告。真实 Pages 部署是否完成，以对应 Actions 日志和正式网址的版本核验为准。

## 本地开发与自动验证

从仓库根目录启动 `python3 -m http.server 8000 --bind 127.0.0.1`。应用本身无需 npm 安装或构建；以下依赖仅用于检查：

```sh
python3 -m pip install -r requirements-test.txt
python3 -m playwright install chromium webkit
python3 scripts/fetch_test_assets.py
HOOPLOG_BROWSER=chromium python3 -m unittest discover -s tests -v
HOOPLOG_BROWSER=webkit python3 -m unittest discover -s tests -v
```

测试使用临时浏览器上下文及合成顾客、照片和表格，不读取正式客户资料。测试包含真实 IndexedDB 和 localStorage 操作；模拟 Google API 的结果不能代替真实账户的授权验收。普通 HTTP 开发时，应用不会自动注册 Service Worker；离线更新测试会在 localhost 安全上下文中显式注册，正式站在 HTTPS 下自动注册。

合成 XLSX 测试使用经校验的 SheetJS 0.18.5，与应用已有的备用解析版本一致；这不代表主 CDN 的 0.20.3 加载或用户原始工作簿已经验证。

发布目录由 `python3 scripts/build_site.py --output _site --commit "$(git rev-parse HEAD)"` 生成，只包含允许公开的页面、Service Worker、manifest 和版本标识，不上传测试、照片、浏览器数据或仓库隐藏文件。

## 第一次使用「冒险」上传

1. 先在 HOOPLOG 既有的「设置」中，确认 Google Cloud **网页 OAuth 客户端 ID** 已填写、Google Drive API 已启用，GitHub Pages 域名已加入允许的 JavaScript 来源；确保 OAuth 同意屏幕允许 `https://www.googleapis.com/auth/drive.file` 权限。个人测试应用还须添加测试用户。
2. 打开底部「冒险」→「云端同步」，点击 **连接 Google Drive**，在弹窗中选择正确的 Google 账户并允许本应用创建和管理自己创建的文件。
3. 默认会在 **我的云端硬盘/冒险** 下新建：`姿势模板/`、`顾客实拍/<顾客>/<姿势>/`，以及 `冒险资料.json`。不会写进篮球记录的「篮球」总文件夹，因为原来的篮球同步会扫描其子文件夹。
4. 完成连接后，每次从图库上传模板或在对照页面上传顾客实拍，将自动上传 Google Drive。仅当返回成功文件 ID 时显示「已同步」。原文件不缩放、不压缩，上传的二进制内容与网页选中的 File 一致。
5. 如果离线、写入授权过期、文件夹无权限或上传失败，照片仍保存在**同一台设备浏览器的 IndexedDB**，显示「待同步」。重新连接后点击「同步待上传」。不要在未同步完成时清除 Safari 网站数据。
6. 更换设备需在另一设备中以同一 Google 账号进入「冒险」→「云端同步」连接并读取数据。Drive 图片默认私有，不会上传 GitHub。

## 指定已有文件夹

「云端同步」有可选 **父文件夹链接 / ID**：留空会在我的云端硬盘创建独立的「冒险」文件夹。指定已有目录可能受 `drive.file` 权限限制，未经应用授权的目录不能直接写入；此时留空使用专属目录，或另外配置 Google Picker 授予目录权限。出于安全考虑，已经有文件上传时禁止直接更换目标父目录，以免旧照片引用失效。

## 同步边界与安全

- 无需服务器或 GitHub 写入权限；在前台由当前浏览器通过 OAuth 向 Google Drive 发起请求。GitHub Pages 只托管代码，**不存储顾客照片**。
- 写入访问令牌仅保留在当前网页内存，不写进源码、localStorage、GitHub 仓库；用 `drive.file` 最小化权限，不把既有篮球只读授权改成全盘读写。
- Google OAuth 令牌会过期；静态网站不能承诺永久免登录或在 Safari 关闭后后台持续同步；遇到期满需要再次连接。
- 两台设备同时编辑同一照片备注可能出现最后写入覆盖，建议避免同时编辑。删除浏览器网站数据前应确认云端成功。
- v18 无服务器端 OAuth 密钥，无人脸识别，也不公开顾客照片。原有篮球视频缓存数据库保留；IndexedDB 升级仅新增 `adventure_media` object store，不清空 `videos`/`folders`。

## 验证范围与限制

- 自动检查覆盖 JavaScript 语法、篮球统计和训练、顾客与多张照片、约拍与评价、持久化、模拟 Drive 同步及离线网页更新。每次结果以该次测试输出为准，不把未执行的项目写为通过。
- Chromium 与 WebKit 的窄屏测试能够发现部分浏览器差异，但不能代替实机 iPhone Safari。
- **真实 Google OAuth 弹窗、Drive 上传和文件夹权限、跨设备恢复、用户原有真实 Excel，以及实机 iPhone Safari：没有对应授权或设备时均标记为未验证。** 请先用非敏感测试照片实际上传，确认云端文件及关联正确后再使用正式客户资料。
