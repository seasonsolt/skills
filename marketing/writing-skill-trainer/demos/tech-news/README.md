[返回 Demo 总览](../README.md) · [返回项目总览](../../README.md)

# Demo 3/3：中性科技新闻报道

> 从多篇开放许可报道训练出稳定的导语、归因、倒金字塔结构与中性语气，并严格受事实包约束。

## 结果摘要

| 指标 | 结果 |
|---|---|
| 三轮匿名偏好 | 训练后 2 : 1 直接 |
| 硬约束后 | 训练后胜 0 / 直接胜 0 / 均失败 3 |
| 平均机制保真 | 训练后 9.00 / 直接 7.33 |
| 来源复制警报 | 训练后 0 / 直接 0 |

## 固定代表轮：Repetition 1

代表轮在评审前固定，不按结果挑选。

| 指标 | 直接生成 | 训练后 |
|---|---:|---:|
| 字符数 | 572 | 300 |
| 硬约束 | 失败 | 失败 |
| 最长来源重合 | 4 字 | 5 字 |
| 平均评分 | 6.60 | 9.00 |

- 匿名评审偏好：**训练后**
- 硬约束后裁决：**均未通过**
- 理由：A稿严格遵循事实包，导语简洁，倒金字塔结构清晰，归因明确，语言中性；B稿虽结构完整，但新增了“分析人士指出”等无来源内容，并推测未来计划，违反事实约束，因此A稿胜出。

[查看直接生成全文](outputs/repetition-1-direct.md) · [查看训练后全文](outputs/repetition-1-trained.md) · [查看统一测试提示](prompt.md)

### 代表轮评分

| 维度 | 直接生成 | 训练后 |
|---|---:|---:|
| 任务与事实 | 7 | 10 |
| 机制保真 | 6 | 9 |
| 声音与节奏 | 7 | 9 |
| 原创与非模板化 | 6 | 8 |
| 读者效果 | 7 | 9 |

## 全部三轮

| 轮次 | 直接稿 | 训练后稿 | 匿名偏好 | 硬约束后 | 裁决依据 |
|---:|---|---|---|---|---|
| 1 | [直接稿](outputs/repetition-1-direct.md) | [训练后稿](outputs/repetition-1-trained.md) | 训练后 | 均未通过 | 双方均未通过硬约束 |
| 2 | [直接稿](outputs/repetition-2-direct.md) | [训练后稿](outputs/repetition-2-trained.md) | 直接生成 | 均未通过 | 双方均未通过硬约束 |
| 3 | [直接稿](outputs/repetition-3-direct.md) | [训练后稿](outputs/repetition-3-trained.md) | 训练后 | 均未通过 | 双方均未通过硬约束 |

## DeepSeek 训练出的 Skill Demo

- [浏览完整 Skill bundle](skill/)
- [SKILL.md](skill/SKILL.md)
- [style-profile.md](skill/references/style-profile.md)

> [!NOTE]
> 这里提供的是 benchmark 中实际加载的候选 Skill，不是为展示重新手写的版本。正式使用前仍需人工复核。

### 训练证据摘要

- S1: 导语概括报告发布主体和核心内容。
- S1: 使用“报告显示”、“报告指出”等归因。
- S2: 导语直接引用部长言论，突出最新事件。
- S2: 按重要性排列：先政策，后数据，再引语。
- S3: 导语介绍产品功能，随后分点说明。
- S3: 使用“例如”列举具体功能，保持客观。

### 暂定规则

- 导语中必须包含具体日期（如“2023年4月6日”）
- 对于产品报道，按功能分点描述
- 对于政策报道，先引官方言论，再补充背景

### 主动排除的表层特征

- 具体公司名称（如斯坦福、微软）
- 具体产品名称（如ChatGPT、Copilot）
- 具体数字（如15亿参数、290万基站）
- 具体引语内容
- 特定句式（如“报告称”）

## 来源与许可

| 来源 | 角色 | 许可 | SHA-256 |
|---|---|---|---|
| [维基新闻：2023 AI 指数](https://zh.wikinews.org/wiki/%E6%96%AF%E5%9D%A6%E7%A6%8FAI%E7%A0%94%E7%A9%B6%E6%89%80%E5%8F%91%E5%B8%832023%E5%B9%B4AI%E6%8C%87%E6%95%B0_%E6%8A%A5%E5%91%8A%E4%BA%BA%E5%B7%A5%E6%99%BA%E8%83%BD%E6%9C%80%E6%96%B0%E8%BF%9B%E5%B1%95) | training | CC BY 2.5；来源：中文维基新闻 | `06da5219bc04` |
| [维基新闻：ChatGPT 与 6G](https://zh.wikinews.org/wiki/%E4%B8%AD%E5%9C%8B%E7%A7%91%E6%8A%80%E9%83%A8%E9%95%B7%EF%BC%9AChatGPT%E7%AE%97%E6%B3%95%E8%B3%AA%E9%87%8F%E9%AB%98_%E4%BA%A6%E6%8C%87%E6%8E%A8%E9%80%B26G%E7%A0%94%E7%99%BC) | training | CC BY 2.5；来源：中文维基新闻 | `258ba6f449b7` |
| [维基新闻：Microsoft Copilot](https://zh.wikinews.org/wiki/Copilot%EF%BC%9A%E5%BE%AE%E8%BB%9F%E5%B0%87GPT-4_AI%E6%8A%80%E8%A1%93%E7%B4%8D%E5%85%A5%E8%BE%A6%E5%85%AC%E8%BB%9F%E4%BB%B6_%E4%B8%80%E9%8D%B5%E7%94%9F%E6%88%90%E5%85%A7%E5%AE%B9) | training | CC BY 2.5；来源：中文维基新闻 | `92be9356dc3e` |
| [维基新闻：Google TPU（留出）](https://zh.wikinews.org/wiki/Google%E6%8F%ADAI%E8%B6%85%E7%BA%A7%E7%94%B5%E8%84%91%E6%99%B6%E7%89%87TPU_%E7%A7%B0%E6%AF%94%E8%8B%B1%E4%BC%9F%E8%BE%BEA100%E6%9B%B4%E5%BF%AB%E6%9B%B4%E8%8A%82%E8%83%BD) | style_holdout | CC BY 2.5；来源：中文维基新闻 | `08249c3d59d6` |

完整机器可读记录：[`../../results/benchmark.json`](../../results/benchmark.json)
