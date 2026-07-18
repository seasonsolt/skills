# AGENTS.md — 丹青 · 小红书 AI 写作工具

本仓库把"小红书从数据诊断到发布"的方法论固化成一套 agent skill。
**任何 AI 写作/编码 agent（Claude Code、Codex、Cursor、Windsurf…）做本仓库相关的活，都应遵循本文件。**

## 方法论在哪（唯一真源）

核心 skill：[`.claude/skills/xiaohongshu-content/SKILL.md`](.claude/skills/xiaohongshu-content/SKILL.md) + 同目录 `references/`（诊断/定位/选题/文案/配图/草稿/发布，外加去 AI 味）。
**做任何小红书相关的任务，先读它，按它走。** 七步链路，哪步都能单独用：

**诊断 → 定位 → 选题 → 文案 → 配图 → 草稿 → 发布**

## 🔴 强制：写正文必须过"去 AI 味"（humanizer-zh）

任何要发布的正文，定稿前**必须过一道 humanizer-zh**——默认执行、不需用户点名、不可跳过：

- **Claude Code**：`/humanizer-zh [正文]`
- **Codex / 其它无斜杠命令的 agent**：读 [`.claude/skills/humanizer-zh/SKILL.md`](.claude/skills/humanizer-zh/SKILL.md)，按其 **24 项 AI 痕迹 + 50 分 rubric** 亲手改写并打分，**≥40/50 才算完成**，不到就继续改，并向用户报一句"改了什么 + 分数"。
- 去味时**事实、数字、出处一律不许改，不许编造第一人称"亲测"经历**（红线，见下）。

## 环境依赖（Codex 尤其注意）

同一条链路里，各步对工具的要求不同：

| 步骤 | 依赖 | 无浏览器的 agent（如纯 Codex）能否独立做 |
|---|---|---|
| 1 诊断 / 6 建草稿 / 7 发布 | **浏览器自动化**（登录 `creator.xiaohongshu.com`） | 否 → 交回用户，或用带浏览器 MCP 的 agent |
| 3 选题 | 混合联网检索（Tavily 可选 + WebSearch/浏览器） | 部分（有联网即可；Tavily 未配置时自动回退） |
| 4 文案 / 去 AI 味 | 纯文本 + 本地命令 | ✅ 能 |
| 5 配图 | 方案 A 使用当前 agent 可用的图像生成工具（Codex 可直接调用 imagegen；没有原生工具时才需浏览器）；**方案 B（HTML/CSS→截图）纯本地、与 agent 无关** | ✅ 可直接走方案 B：`assets/card-template/` 或参考 `posts/*/cards/_build.py`；若当前环境有 imagegen，也可走方案 A |

**没有浏览器工具时**：专注做 3/4/5（选题、文案+去味、原生 imagegen 或 HTML/CSS 出图），把 1/6/7 明确交回用户，别假装完成。

## 红线（与 skill 一致，最高优先级）

- **合规第一**：不做订阅/跨区购买/境外账号获取/翻墙类内容（小红书明令禁止，会下架甚至处罚）。
- **账号信息**走 `.env`（已 `.gitignore` 排除），不硬编码、不提交。
- **`posts/`** 是用户私人发布归档：**绝不进任何公开仓库、不外发**、改写前先读别乱删。是否提交到你自己的**私有**仓库由使用者决定（本 danqing 仓已转 Private，`posts/` 在这里正常入库）。
- **真实性**：文案里的"亲测/我的用法"必须真；转载标清出处，别包装成原创。

## 提交约定

- 默认在分支上改；`.env` 永不提交，`posts/` 绝不进任何公开仓库；commit 说明用中文、讲清价值。
- `.claude/skills/humanizer-zh/` 是 vendored（op7418/Humanizer-zh，MIT），保留其 LICENSE 与出处。

## 公开分发副本（seasonsolt/skills）

本仓库的可复用技能对外发布在公开仓库 **[seasonsolt/skills](https://github.com/seasonsolt/skills)**（`skills/xiaohongshu-content/`、`skills/humanizer-zh/`）。

- **真源始终是本仓 `.claude/skills/`**；公开仓是下游镜像，别在公开仓直接改。
- 改完技能后用 `python scripts/publish_skills.py --target <skills 工作副本>` 装配同步，复核后加 `--push` 推送。
- 装配时会把 `assets/card-template/`、`examples/note.template.md`、`AGENTS.md`、`CONTEXT.md` 一并打包进技能目录，使公开副本自洽；`posts/`、`.env` 等私人内容永不外发。
