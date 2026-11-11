# HOOPLOG 开发约定

## 架构与代码来源

- 仓库：`fjnanyuan/basketball-vidoe`；正式站：`https://fjnanyuan.github.io/basketball-vidoe/`。
- 当前业务版本为 v18。GitHub Pages 托管静态页面；`index.html` 包含主要 HTML、CSS 和 JavaScript，`sw.js` 缓存网页外壳，`manifest.webmanifest` 提供安装信息。没有应用服务器或业务构建依赖。
- 开工先检查工作区、读取仓库当前指令，获取 `origin/main` 最新提交，并核对与本地的差异。当前仓库代码是可信来源，不能根据历史聊天重建项目。
- 使用当前隔离环境的已有检出；未经要求不创建 Git worktree。保留用户未提交的修改。
- 界面以中文为主，优先适配 iPhone Safari。只改已经确认有问题的必要代码，不增加本次需求以外的业务功能。

## 必须保留的行为

- 篮球：Google Drive Excel 读取、单场统计、多场汇总、训练对比、视频筛选与原始离线视频缓存。保留已有字段、其他动作和 Excel 兼容逻辑；同一天不同训练文件夹独立统计。
- 五项主要投篮动作依次是：原地投篮、一次突破上篮、篮下反篮、篮下直接终结、一次突破急停跳投。
- 对比设置默认折叠；自动选择最新一场及之前最多三场相同星期的训练；支持手动选场和恢复自动推荐；分别显示出手、命中、命中率。直线趋势箭头使用绿色上升、红色下降、灰色持平，保留按指标基准和平滑非线性曲线计算角度的逻辑。
- 反应训练：保留方向、前脚、前脚加协防三种模式，右 60% / 左 40%，6/7/8/9 秒、隐藏答案、大画面、每日目标及本机历史。提示次数不能描述为摄像头验证的完成次数。
- 冒险：保留模板图库、独立顾客、约拍清单、模板与实拍对照、技巧、备注和评价。同一模板可供多个顾客使用；同一顾客与模板可以追加多张实拍，不能覆盖历史照片或泄漏其他顾客记录。
- Drive：模板与实拍分目录，保留原文件，支持有权限的父文件夹；失败保持待同步并可重试，只有 Drive 返回成功文件 ID 才显示已同步；索引必须可恢复关联、约拍和评价。

## 数据与凭据保护

- 不清空、重建或改名现有 IndexedDB 数据库、`folders` / `videos` / `adventure_media` 存储，也不清除 localStorage 训练历史来解决问题。涉及数据迁移必须另行说明、测试并取得用户确认。
- Service Worker 更新只处理应用网页缓存，不能清除照片、视频或训练数据；要验证已有数据在更新前后保持不变。
- 真实照片、客户资料、OAuth Token、密钥及浏览器配置文件不得提交 Git；自动测试只使用生成的测试数据和隔离浏览器上下文。
- OAuth Token 只保存在网页内存。保持篮球 `drive.readonly` 与摄影 `drive.file` 的权限边界；不能假设 `drive.file` 可访问任意既有文件夹。
- OAuth 客户端 ID 通过应用设置填写；不向用户索要聊天中的访问令牌或客户端密钥。缺少授权时明确报告真实 Drive 验证未完成。

## 分支、PR 与发布

1. 需求提出后读取最新 `main`，在独立功能或修复分支修改。
2. 复现问题后做最小修复，补充能覆盖问题的回归测试，完成相关功能验收。
3. 提交 PR，说明问题、原因、改动、验证结果和未验证项，提供预览材料。不能把语法通过当成功能验证。
4. 等待用户明确确认后才合并 `main`。不得直接推送覆盖 `main`、自行合并或触发生产发布；不要重跑旧的生产部署来验证 PR。
5. 经确认合并后，`main` 工作流通过测试才部署 Pages，并校验正式站的提交标识及资源内容。失败时检查具体 job/step 日志，不将排队、JavaScript、缓存或授权混为同一原因。
6. GitHub Pages 首次切换到自定义工作流前，在仓库 Settings → Pages 将 Source 设为 GitHub Actions；此操作与 PR 合并都需要按用户授权进行。分支型 Pages 在迁移期间可能仍由平台部署，不能把新增 YAML 视为迁移已经完成。

## 本地开发与验证

在仓库根目录运行静态服务器：

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

测试依赖与浏览器：

```sh
python3 -m pip install -r requirements-test.txt
python3 -m playwright install chromium webkit
python3 scripts/fetch_test_assets.py
HOOPLOG_BROWSER=chromium python3 -m unittest discover -s tests -v
HOOPLOG_BROWSER=webkit python3 -m unittest discover -s tests -v
```

Linux 缺少浏览器系统库时，按环境支持的安装方式补齐；GitHub Actions 使用 `python -m playwright install --with-deps <browser>`。保留 TLS、签名及校验和验证。

- 自动测试需要实际执行，保留底层退出码；失败、跳过和未执行必须分别报告。
- 至少覆盖相关篮球统计、自动与手动选场、训练计数与持久化、顾客隔离、多张照片、评价、约拍、离线缓存及更新后的数据保留。
- 模拟 OAuth/Drive 测试只证明请求、状态与恢复逻辑；不能宣称真实 Google 账户、文件夹权限和跨设备恢复已通过。
- 使用 Playwright Chromium 与 WebKit 检查窄屏布局及操作。WebKit 不是实机 iPhone Safari，实机未测必须说明。
- 不把任何客户原始 Excel 或照片放入测试夹具；使用合成表格和图片，并说明原有真实 Excel 是否得到授权验证。

生成待部署内容及核验生产版本：

```sh
python3 scripts/build_site.py --output _site --commit "$(git rev-parse HEAD)"
python3 scripts/verify_deployment.py --url https://fjnanyuan.github.io/basketball-vidoe/ --commit "$(git rev-parse HEAD)"
```

`_site` 只包含公开静态文件和版本标识。PR 工作流生成可下载的预览构建；它不是在线 PR 预览地址。没有配置独立预览托管时，提供截图及测试报告，并明确说明这一限制。
