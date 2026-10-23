# HOOPLOG v3：Excel D列匹配文件夹名

## Google Drive 目录
南球/
  篮球记录.xlsx
  1021舟山B面/
    IMG_0001.mp4
  1028舟山B面/
    IMG_0002.mp4

## 匹配规则
- Excel D列（第4列）填写**完整子文件夹名称**，如 `1021舟山B面`。
- 只做文件夹名称一致匹配，不再使用日期字段。
- 匹配时忽略名称两端空格、名称中空白字符、全半角差异和英文字母大小写；其他字必须一致（`舟山`与`周三`不会被当成相同）。
- 在匹配的文件夹内，继续以 Excel「片段编号」和视频原始文件名关联。
- Excel 位于「南球」总文件夹根目录，支持 xlsx/csv。
- 网站同步文件列表和 Excel 时不会下载视频内容；缓存视频仍须两次确认 Wi-Fi。

## 更新 GitHub Pages
在仓库 `fjnanyuan/basketball-vidoe` 根目录覆盖 `index.html` 和 `sw.js`，可同时覆盖 `manifest.webmanifest`，提交后等待 Pages 部署。重新打开网站，进入「文件夹」点击「同步子文件夹与 Excel」。无需重新配置 Google OAuth。
