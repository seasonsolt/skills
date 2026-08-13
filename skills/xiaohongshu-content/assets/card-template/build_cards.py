#!/usr/bin/env python3
"""
丹青 · 图文卡片渲染器（Claude design 方案 B）
把 HTML/CSS 渲染成 1080×1440 的小红书图文卡 —— 中文像素级精确、零错字、完全可控，
不依赖 AI 出图。当 gpt image2 失败/限流时用这套，也用它保证整个系列视觉统一。

用法：
  1. 按 THEMES.md 路由表选主题，改 THEME；BADGE 改成你的署名。
  2. 改下面 CARDS 里每张卡的中文内容（inner HTML）。
  3. python3 build_cards.py
  4. 生成 P1-*.png … Pn-*.png（1080×1440）。

依赖：本机 Google Chrome（headless 截图）。macOS 路径见 CHROME，其它系统自行改。

主题：themes/<name>.css 定义视觉，themes/<name>.decor.html（可选）是卡内装饰层。
所有主题共用同一套 class 词汇表——同一份 CARDS 换 THEME 即整套换肤：
  tag / h1 / h2 / kicker / body-md / strong / red / hl / sub / quote-block / note-sm / list / decide / cta / badge
语义：.red = 主题强调色（不一定是红），.hl = 主题高亮。
"""
import subprocess, os

OUT = os.path.dirname(os.path.abspath(__file__))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
THEME = "paper"   # ← receipt | vintage | matrix | bulletin | paper，按 THEMES.md 选
BADGE = "你的署名 · 你的系列 #1"   # ← 改成你的

CSS = open(os.path.join(OUT, "themes", THEME + ".css")).read()
_decor = os.path.join(OUT, "themes", THEME + ".decor.html")
DECOR = open(_decor).read() if os.path.exists(_decor) else ""

# ← 在这里编辑每张卡。第一个元素是文件名，第二个是卡内 HTML（装饰层自动注入，不用写）。
CARDS = [
  ("P1-cover", f"""
    <div class="main" style="justify-content:center;">
      <div class="tag">小标签 / 权威钩</div>
      <h1>封面主标题，<br>关键词<span class="red">强调</span></h1>
      <div class="sub">一句副标题，交代身份或角度</div>
    </div>
    <div class="badge">{BADGE}</div>
  """),
  ("P2-example", f"""
    <div class="main">
      <div class="kicker">一句抓人的短句。</div>
      <div class="body-md">正文说明，<span class="hl">概念用高亮</span>，<span class="red">重点用强调色</span>。</div>
      <div class="body-md strong">一句加粗的落点。</div>
    </div>
    <div class="badge">{BADGE}</div>
  """),
  ("P3-quote", f"""
    <div class="main">
      <div class="tag">引用/专家</div>
      <div class="quote-block">「一段引用，用左边框突出。」</div>
      <div class="note-sm">—— 出处</div>
    </div>
    <div class="badge">{BADGE}</div>
  """),
]

# receipt 主题的 .card 是暗色台面，内容需包在白色小票 .slip 内。
SLIP_THEMES = {"receipt"}

for name, inner in CARDS:
    body = f"<div class='slip'>{DECOR}{inner}</div>" if THEME in SLIP_THEMES else f"{DECOR}{inner}"
    doc = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div class='card'>{body}</div></body></html>"
    hp = os.path.join(OUT, f"_{name}.html"); pp = os.path.join(OUT, f"{name}.png")
    open(hp, "w").write(doc)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        f"--screenshot={pp}", "--window-size=540,720", "--force-device-scale-factor=2", hp],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(hp)
    print(name, "->", os.path.exists(pp))
