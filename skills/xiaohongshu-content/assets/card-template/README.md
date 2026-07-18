# 图文卡片渲染器（HTML/CSS 确定性渲染）

把 HTML/CSS 渲染成 1080×1440 的小红书图文卡。**中文像素级精确、零错字、完全可控，不依赖 AI 出图。** Codex、Claude Code 或其他能编辑文件并运行本地渲染器的 agent 都可以使用。

## 什么时候用
- AI 出图（gpt image2 等）失败 / 限流 / 中文渲染糊时的**兜底**；
- 想让整个系列**视觉统一**时的**主力**——同一套 CSS 出的卡天然一致。

对文字密集的知识卡，这套通常比 AI 出图更稳。

## 用法
```bash
cp -r assets/card-template posts/<你的笔记>/cards   # 复制一份到你的笔记目录
# 编辑 build_cards.py 里的 CARDS（每张卡的中文）和 BADGE（署名）
python3 build_cards.py                              # 生成 P1-*.png … Pn-*.png
```

## 视觉约定
浅米底 `#f4f2ee` · 左上大引号装饰 · 大字标题 · 红 `#d63a2c` 强调 · 黄 `#ffe27a` 高亮 · 大量留白 · 3:4。
换你自己的品牌色就改 CSS 里那两个色值。

## 依赖
本机 Google Chrome（用 headless 截图）。macOS 路径已写死在脚本里，其它系统改 `CHROME` 变量。
