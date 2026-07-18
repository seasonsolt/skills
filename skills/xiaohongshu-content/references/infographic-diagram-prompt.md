# Infographic Diagram · 复杂技术概念提示词模板

用于把包含多个组成部分、关系或反馈回路的复杂技术概念画成一张**横向、无正文的编辑型科学信息图**。先完成下方变量表，再复制母提示词。

## 变量

| 变量 | 填写要求 |
|---|---|
| `SUBJECT` | 一句话写清具体系统或机制，以及图要解释什么 |
| `NUMBER` | 上方主要科学形式的数量，通常 3–7 个 |
| `CONTENT CATEGORIES` | 下方信息模块的同层级分类，用逗号分隔 |
| `RELATIONSHIP` | 主体间的关系：流程、依赖、反馈、对照或层级 |

`NUMBER` 必须与概念拆解后的核心组成数量一致；`CONTENT CATEGORIES` 应互斥，避免把“组件、优势、步骤”这类不同层级混在一排。

## 母提示词

```text
Use case: infographic-diagram

Primary request:
Create a wide editorial infographic about [SUBJECT].
Represent the relationship as [RELATIONSHIP].
Use the supplied image only as a visual style reference. Preserve its visual language,
materials, line treatment, palette, density, and diagrammatic character, but do not
reproduce its particular objects, icons, layout, or content.

Visual language:
A retro-futurist scientific atlas combining an antique astronomical manuscript,
precision engineering blueprint, archival encyclopedia plate, and restrained
mid-century editorial information design.

Medium and rendering:
Hand-drawn technical illustration on warm aged ivory paper.
Extremely fine ink linework, drafting-pencil construction lines, compass arcs,
concentric circles, geometric lattices, coordinate marks, measurement ticks,
orbital paths, crosshair alignments, and subtle stippling.
Slightly imperfect analog registration and restrained ink bleeding.
The illustration must feel carefully drafted by hand, not digitally vector-perfect.

Composition:
[NUMBER] large symbolic scientific forms arranged across the upper two-thirds,
connected by thin mechanical or orbital guide lines that clearly express [RELATIONSHIP].
A corresponding row of framed information modules occupies the lower third.
Strong horizontal reading direction, generous negative space, precise alignment,
clear visual hierarchy, and a quiet underlying modular grid.
Use asymmetrical visual weight while keeping the full composition balanced.

Information modules:
Each lower module contains a small family of minimal technical pictograms related
to [CONTENT CATEGORIES].
Icons use consistent thin-line geometry, simple diagrams, sparse fills, and ample
internal spacing.
Keep all symbols visually coherent and avoid modern app-interface styling.

Palette:
Warm parchment, faded charcoal-black, muted blue-green, oxidized vermilion,
and a small amount of luminous amber-gold.
Use no more than four principal ink colors.
Color should appear printed, weathered, and slightly desaturated rather than bright
or digitally saturated.

Paper and atmosphere:
Subtle fibrous paper grain, faint stains, light foxing, softly worn edges,
barely visible grid lines, registration dots, marginal construction marks,
and delicate archival imperfections.
The paper texture must remain quiet enough that the diagrams stay crisp.

Style priorities:
Precision without sterility.
Complexity without clutter.
Ancient scholarship interpreted through speculative future technology.
Elegant, mysterious, analytical, archival, and highly legible.
The image should look like a rediscovered scientific plate from an alternate history.

No readable body text is required. Use pictograms and abstract diagrammatic marks
instead of invented lettering.

Avoid:
photorealism, glossy 3D rendering, neon cyberpunk colors, heavy steampunk machinery,
thick comic outlines, watercolor washes, ornate fantasy decoration, modern dashboard UI,
plastic gradients, excessive distressing, random illegible typography, dense labels,
perfectly clean vector graphics, or copying the reference composition.
```

## 使用约束

- 没有参考图时，删除“supplied image”两句，不要假装存在参考图。
- 参考图只控制视觉语言，不控制内容结构；新图的主体、图标和布局必须从 `SUBJECT` 重新推导。
- 模板默认输出横向母图，不直接当作 1080×1440 小红书成品卡。
- 需要中文标题、标签或解释时，先生成无字母图，再通过 HTML/CSS 叠字，避免模型生成乱码。
- 一张图只表达一种主要关系。若流程和层级同时重要，拆成两张图或两页卡片。
