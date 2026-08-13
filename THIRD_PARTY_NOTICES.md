# 第三方来源与许可证说明

本文件记录已知的 vendored 内容、样本材料和从其他代码库迁移的来源。它不是根许可证的替代品。

## 独立许可内容

### `skills/humanizer-zh/`

- 本仓状态：Vendored。
- 来源：[`op7418/Humanizer-zh`](https://github.com/op7418/Humanizer-zh)，其说明注明核心内容翻译自 [`blader/humanizer`](https://github.com/blader/humanizer)，并参考 [`hardikpandya/stop-slop`](https://github.com/hardikpandya/stop-slop)。
- 许可证：MIT；版权声明与完整条款保留在 [`skills/humanizer-zh/LICENSE`](skills/humanizer-zh/LICENSE)。
- 本说明不改变各上游项目对其自身内容的许可范围。

### `skills/xiaohongshu-content/`

- 本仓状态：First-party；本公开目录现在是可直接贡献的维护源。
- 来源：最初从维护者的 `seasonsolt/danqing` 仓库装配发布；该上游为私有仓库，核验基准 commit 为 `412ddd423133d374ff290d7e877d127adec8d8ee`。
- 许可证：上游根许可证为 MIT，版权人为 `seasonsolt`；许可证副本保留在 [`skills/xiaohongshu-content/LICENSE`](skills/xiaohongshu-content/LICENSE)。
- 本公开目录包含后续公共化修改，不再要求贡献者回到私有上游修改。

### `marketing/writing-skill-trainer/` 的来源材料

- 《红楼梦》和鲁迅作品样本：Public Domain（公版）。
- 中文维基新闻样本：CC BY 2.5。
- 每篇材料的来源 URL、用途与 SHA-256 摘要记录在对应 Demo 的“来源与许可”表中：[`red-chamber`](marketing/writing-skill-trainer/demos/red-chamber/)、[`restrained-satire`](marketing/writing-skill-trainer/demos/restrained-satire/) 和 [`tech-news`](marketing/writing-skill-trainer/demos/tech-news/)。
- 来源材料的许可证不自动覆盖本仓脚本、说明或生成产物；后者仍受各自适用权利与待确认的根许可证约束。

## 来源已记录、许可证范围待确认

### `skills/java-unit-test-hardening/`

该 skill 从 `xjjk/ai-workspace` 的 `feature-20260714-ut-hardening-entry` 分支迁移并做公共化适配。来源 commit、作者、路径和修改范围见 [`skills/java-unit-test-hardening/UPSTREAM.md`](skills/java-unit-test-hardening/UPSTREAM.md)。当前仓库没有记录该上游内容适用于本仓再分发的独立许可证；根许可证确定前不得据此推定许可。

## 根许可证待确认

除上述明确带独立许可证或来源材料许可的范围外，本仓目前没有根 `LICENSE`。公开可见不等于获得复制、修改或再分发许可；维护者确认权属和兼容性后再添加根许可证，并同步更新本文件。
