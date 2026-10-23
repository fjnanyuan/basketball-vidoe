# HOOPLOG：GitHub Pages + Google Drive + 本机离线视频

这是一个不需要自建后端的个人篮球记录网站。**视频不上传 GitHub**：网页通过你的 Google 账户读取 Google Drive 中的私人日期文件夹，点击「一键缓存」把每个视频保存在手机浏览器的 IndexedDB，断网后只读取本地视频。

## 一、部署到 GitHub Pages

1. 在 GitHub 新建仓库，例如 `hooplog`，上传同目录下的 `index.html`、`sw.js`、`manifest.webmanifest`（这三个文件必须位于仓库根目录）。
2. GitHub 仓库 Settings → Pages → Build and deployment → Deploy from a branch → `main` / `(root)` → Save。
3. 等 GitHub Pages 发布后，访问 `https://你的用户名.github.io/hooplog/`。不要通过 GitHub 文件预览或 `file://` 打开；离线功能需要 HTTPS + Service Worker。
4. 在 iPhone 上建议 **Safari → 分享 → 添加到主屏幕**；联网打开一次，确认网站页面被离线脚本缓存后再测试飞行模式。

## 二、一次性的 Google OAuth 配置

1. 打开 [Google Cloud Console](https://console.cloud.google.com/)，新建项目。
2. APIs & Services → Library → 启用 **Google Drive API**。
3. 配置 Google Auth Platform 的 OAuth 同意页面。个人使用可采用 **Testing** 模式，把你的 Google 账号添加为 **Test user**。
4. 创建 **OAuth 2.0 Client ID**，应用类型：**Web application**。
5. Authorized JavaScript origins 填入 `https://你的用户名.github.io`（注意是域名，不包含 `/hooplog/` 路径）。
6. 复制以 `.apps.googleusercontent.com` 结尾的 Client ID，到网站「设置」里保存，再点击 Google 登录。不要放 Client Secret！
7. 本应用请求 `https://www.googleapis.com/auth/drive.readonly` 读取权限（属于 Google **Restricted scope**）。仅个人测试模式更容易开始，向大众公开提供服务需要按 Google 要求完成权限审查/验证；测试模式授权也可能到期，需要重新授权。

> OAuth Client ID 可以放在静态网站，**Client Secret 和 Access Token 不要写进 GitHub 文件**。本程序的 Access Token 只保存在页面运行内存，不上传到 Github，不写入 localStorage。

## 三、日常使用

1. 在 Google Drive 创建日期文件夹，例如 `2026-10-21_小岩B面`，上传你剪辑的 MP4 / MOV 和当日 Excel。允许存在子文件夹。
2. 复制日期文件夹的 URL，粘贴在网站「文件夹 → 读取文件夹」。不需要把文件夹设成公开。
3. 若 Excel 在该文件夹中，点 **读取文件夹内的 Excel**；也可以在手机本地选择 Excel/CSV 导入。若导入的是包含多日期的大工作簿，网站根据文件夹名称的日期筛选对应行。
4. 在家连接 Wi-Fi，核对手机系统 Wi-Fi 状态，在「文件夹」勾选确认，再点 **一键缓存全部视频**。保持 Safari 在前台，直到全部完成。已成功缓存的文件可以跳过，失败可以重试。
5. 出门以后进入「视频片段」点击显示 **已离线** 的视频。在线播放被禁止：没有缓存的文件会提示不能播放。
6. 存储空间紧张时，点击 **删除此日期缓存**。这个操作只删本机 IndexedDB 视频副本，不删 Google Drive 文件，也不删本机 Excel 统计与备注。

## 四、Excel 格式（沿用你的原表）

自动寻找包含 `日期`、`片段编号`、`动作类型`、`结果`、`备注` 的表头，优先选工作表名包含「小岩」但不包含「汇总」的工作表。按 **A:F** 原始记录进行统计，不读取右侧手工汇总公式。

| 日期 | 片段编号 | 动作类型 | 结果 | 备注 | 场次数 |
|---|---|---|---|---|---|
| 2026/10/21 | IMG_4821.MP4 | 原地投篮 | 成功 | 动作稳定 |  |
| 2026/10/21 | IMG_4822.MP4 | 突破上篮 | 失败 | 脚步问题 |  |

Excel 中的编号与 Google Drive 文件名**完全一致**最好；允许 Excel 带或不带 `.mp4` 后缀，不需要改成从 001 开始。匹配以文件夹 + 完整文件名为准；如果一个日期下有两个同名视频文件，需先改名以保证唯一。

此版本读取 `.xlsx` 需要联网从 SheetJS CDN 下载解析脚本；如果解析脚本无法加载，请在 Excel 中另存为 CSV 后导入。CSV 可以直接在浏览器内解析。**影片离线播放不依赖 SheetJS**。

## 五、Wi-Fi 限制的重要说明

**iPhone Safari / PWA 没有可依赖的公开 API 来确认当前确实是 Wi-Fi。** 本应用：
- 不会自动下载视频，必须手动按按钮且勾选 Wi-Fi 确认；
- 在可识别蜂窝网络的浏览器中阻止下载，下载中识别到变更后立即中止；
- 在 iPhone 网络类型不可知时只能依赖你手动核对，**不能提供系统级严格的“蜂窝永不下载”保证**；
- 片段播放器只打开已存储 Blob，不会尝试在线获取视频；
- 元数据读取、Google 登录、Excel CDN 仍可能消耗少量流量。

如果“连误点都不允许通过移动数据下载视频”是硬要求，需要做 iOS 原生 App，由系统网络接口准确判断 Wi-Fi，再执行下载。

## 六、存储可靠性与隐私

- 手机上视频被存入浏览器 IndexedDB；浏览器存储有配额，可能因存储不足、系统清理、删除站点数据、改设备而丢失。
- 不保证浏览器可以在后台持续下载全部视频；下载时请打开前台，并保持屏幕唤醒。
- 下载逐文件完成、逐文件保存；取消或中断后，已经成功保存的视频还在，下次可继续。
- 个人视频在 Google Drive 里保持私密；**GitHub Pages 公开的是网页源代码**，不是视频文件。但有能力打开网页的人仍会看到通用 UI；Google API 必须用你的 Google 账号授权。
- 特别大（例如几十 GB）的文件夹建议分批操作，并留出充足手机空间；Safari 可能拒绝写入或回收缓存。
- 本项目没有内置云数据库，Excel 分析内容和已缓存视频保存在**当前设备**，换手机不会自动同步；重新从 Drive 读取并导入即可。

## 项目文件

- `index.html`：界面、Google Drive API、Excel 导入、数据统计、IndexedDB 视频缓存和离线播放器。
- `sw.js`：离线缓存网站页面；不会截取 Google Drive 的视频请求。
- `manifest.webmanifest`：手机添加主屏幕信息。
