#!/usr/bin/env python3
"""
丹青 · 图文卡片渲染器（Claude design 方案 B）
把 HTML/CSS 渲染成 1080×1440 的小红书图文卡 —— 中文像素级精确、零错字、完全可控，
不依赖 AI 出图。当 gpt image2 失败/限流时用这套，也用它保证整个系列视觉统一。

用法：
  1. 改下面 CARDS 里每张卡的中文内容（inner HTML），BADGE 改成你的署名。
  2. python3 build_cards.py
  3. 生成 P1-*.png … Pn-*.png（1080×1440）。

依赖：本机 Google Chrome（headless 截图）。macOS 路径见 CHROME，其它系统自行改。

样式约定（系列视觉）：
  浅米底 #f4f2ee · 左上大引号装饰 · 大字标题 · 红(#d63a2c)强调 · 黄(#ffe27a)高亮 · 大量留白 · 3:4。
可用 class：tag / h1 / h2 / kicker / body-md / strong / red / hl / sub / quote-block / note-sm / list / decide / cta / badge
"""
import subprocess, os

OUT = os.path.dirname(os.path.abspath(__file__))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BADGE = "你的署名 · 你的系列 #1"   # ← 改成你的

CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body { width:540px; height:720px; background:#f4f2ee;
  font-family:'PingFang SC','Hiragino Sans GB',system-ui,sans-serif; color:#20201e; }
.card { width:540px; height:720px; padding:52px 48px 44px; position:relative; display:flex; flex-direction:column; }
.quote { position:absolute; top:34px; left:44px; font-family:Georgia,serif; font-size:120px; line-height:1; color:#d9d3c7; font-weight:700; }
.main { flex:1; display:flex; flex-direction:column; justify-content:center; gap:22px; margin-top:40px; }
.tag { font-size:24px; font-weight:800; color:#20201e; }
h1 { font-size:52px; font-weight:900; line-height:1.2; }
h2 { font-size:36px; font-weight:800; line-height:1.32; }
.kicker { font-size:40px; font-weight:900; line-height:1.3; }
.body-md { font-size:28px; line-height:1.62; color:#4a4844; }
.strong { font-weight:800; color:#20201e; }
.red { color:#d63a2c; font-weight:900; }
.hl { background:#ffe27a; padding:0 6px; border-radius:4px; font-weight:800; color:#20201e; }
.sub { font-size:24px; color:#6f6b62; margin-top:6px; }
.quote-block { font-size:29px; line-height:1.55; color:#33322f; font-weight:700; border-left:5px solid #d63a2c; padding-left:20px; }
.note-sm { font-size:23px; line-height:1.5; color:#8a867d; }
.list { font-size:27px; line-height:1.9; color:#33322f; }
.decide { font-size:38px; font-weight:900; line-height:1.35; color:#20201e; }
.cta { font-size:23px; line-height:1.7; color:#5a574f; }
.badge { position:absolute; bottom:40px; right:48px; font-size:19px; color:#b7b2a6; font-weight:700; }
"""

# ← 在这里编辑每张卡。第一个元素是文件名，第二个是卡内 HTML。
CARDS = [
  ("P1-cover", f"""
    <div class="quote">&ldquo;</div>
    <div class="main" style="justify-content:center;">
      <div class="tag" style="color:#8a867d;">小标签 / 权威钩</div>
      <h1>封面主标题，<br>关键词<span class="red">红字强调</span></h1>
      <div class="sub">一句副标题，交代身份或角度</div>
    </div>
    <div class="badge">{BADGE}</div>
  """),
  ("P2-example", """
    <div class="quote">&ldquo;</div>
    <div class="main">
      <div class="kicker">一句抓人的短句。</div>
      <div class="body-md">正文说明，<span class="hl">概念用黄高亮</span>，<span class="red">重点用红</span>。</div>
      <div class="body-md strong">一句加粗的落点。</div>
    </div>
  """),
  ("P3-quote", """
    <div class="quote">&ldquo;</div>
    <div class="main">
      <div class="tag">引用/专家</div>
      <div class="quote-block">「一段引用，用左红边框突出。」</div>
      <div class="note-sm">—— 出处</div>
    </div>
  """),
]

for name, inner in CARDS:
    doc = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div class='card'>{inner}</div></body></html>"
    hp = os.path.join(OUT, f"_{name}.html"); pp = os.path.join(OUT, f"{name}.png")
    open(hp, "w").write(doc)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        f"--screenshot={pp}", "--window-size=540,720", "--force-device-scale-factor=2", hp],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(hp)
    print(name, "->", os.path.exists(pp))
