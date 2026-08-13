# 图文卡片渲染器（HTML/CSS 确定性渲染）

把 HTML/CSS 渲染成 1080×1440 的小红书图文卡。**中文像素级精确、零错字、完全可控，不依赖 AI 出图。** Codex、Claude Code 或其他能编辑文件并运行本地渲染器的 agent 都可以使用。

## 什么时候用
- AI 出图（gpt image2 等）失败 / 限流 / 中文渲染糊时的**兜底**；
- 想让整个系列**视觉统一**时的**主力**——同一套 CSS 出的卡天然一致。

对文字密集的知识卡，这套通常比 AI 出图更稳。

## 用法
```bash
cp -r assets/card-template posts/<你的笔记>/cards   # 复制一份到你的笔记目录
# 1. 读 THEMES.md 路由表选主题，改 build_cards.py 的 THEME
# 2. 编辑 CARDS（每张卡的中文）和 BADGE（署名）
python3 build_cards.py                              # 生成 P1-*.png … Pn-*.png
```

## 主题
五套主题共用同一套 class 词汇表，换 `THEME` 即整套换肤（预览见 `previews/`）：
`receipt` 收银小票（价格/成本）· `vintage` 仿古版画（系列主视觉）· `matrix` CRT 数字雨（极客题材）· `bulletin` 黑底号外（事件贴）· `paper` 浅米引纸（轻内容）。
选择规则和 P1 图像模型 prompt 种子见 `THEMES.md`。`.red` = 主题强调色，`.hl` = 主题高亮。

## 依赖
本机 Google Chrome（用 headless 截图）。macOS 路径已写死在脚本里，其它系统改 `CHROME` 变量。
