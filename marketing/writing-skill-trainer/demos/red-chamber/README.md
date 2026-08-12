[返回 Demo 总览](../README.md) · [返回项目总览](../../README.md)

# Demo 1/3：《红楼梦》章回体续写

> 从多章样本学习文白相间的叙事、以行动和对话显露人物关系、含蓄推进情绪，而非堆砌古语。

## 结果摘要

| 指标 | 结果 |
|---|---|
| 三轮匿名偏好 | 训练后 3 : 0 直接 |
| 硬约束后 | 训练后胜 2 / 直接胜 1 / 均失败 0 |
| 平均机制保真 | 训练后 9.00 / 直接 8.00 |
| 来源复制警报 | 训练后 0 / 直接 0 |

## 固定代表轮：Repetition 1

代表轮在评审前固定，不按结果挑选。

| 指标 | 直接生成 | 训练后 |
|---|---:|---:|
| 字符数 | 1029 | 912 |
| 硬约束 | 通过 | 通过 |
| 最长来源重合 | 3 字 | 3 字 |
| 平均评分 | 8.40 | 9.20 |

- 匿名评审偏好：**训练后**
- 硬约束后裁决：**训练后**
- 理由：两稿均符合任务要求，但A稿在叙事自然度、人物区分度和含蓄收束上更胜一筹，B稿稍显平直。A稿以水痕喻泪的结尾尤为精妙，故判A胜。

[查看直接生成全文](outputs/repetition-1-direct.md) · [查看训练后全文](outputs/repetition-1-trained.md) · [查看统一测试提示](prompt.md)

### 代表轮评分

| 维度 | 直接生成 | 训练后 |
|---|---:|---:|
| 任务与事实 | 10 | 10 |
| 机制保真 | 8 | 9 |
| 声音与节奏 | 8 | 9 |
| 原创与非模板化 | 8 | 9 |
| 读者效果 | 8 | 9 |

## 全部三轮

| 轮次 | 直接稿 | 训练后稿 | 匿名偏好 | 硬约束后 | 裁决依据 |
|---:|---|---|---|---|---|
| 1 | [直接稿](outputs/repetition-1-direct.md) | [训练后稿](outputs/repetition-1-trained.md) | 训练后 | 训练后 | 匿名质量裁决 |
| 2 | [直接稿](outputs/repetition-2-direct.md) | [训练后稿](outputs/repetition-2-trained.md) | 训练后 | 训练后 | 硬约束覆盖质量偏好 |
| 3 | [直接稿](outputs/repetition-3-direct.md) | [训练后稿](outputs/repetition-3-trained.md) | 训练后 | 直接生成 | 硬约束覆盖质量偏好 |

## DeepSeek 训练出的 Skill Demo

- [浏览完整 Skill bundle](skill/)
- [SKILL.md](skill/SKILL.md)
- [style-profile.md](skill/references/style-profile.md)

> [!NOTE]
> 这里提供的是 benchmark 中实际加载的候选 Skill，不是为展示重新手写的版本。正式使用前仍需人工复核。

### 训练证据摘要

- 以行动和对话显露人物关系：S2中黛玉进贾府，通过座位、称呼、礼物等细节暗示亲疏。
- 含蓄推进情绪：S1中甄士隐梦醒后见女儿，情绪通过动作（抱、看）表达。
- 文白相间：S1、S2、S3中白话为主，穿插文言词汇如“因”“故”“遂”。
- 结构因果：S2中雨村得信后谋职，通过对话和行动推进。
- 人物出场通过他人视角：S2中王熙凤出场，先闻其声，再写外貌。
- 日常场景用对话推进：S2中贾母与黛玉对话，展现关系。
- 梦境幻境用象征：S3中太虚幻境、判词等象征人物命运。

### 暂定规则

- 每回结尾以景物或动作收束，不点破情绪。
- 人物对话中隐含身份和关系，不直接说明。
- 梦境场景使用象征和隐喻，不直白解释。

### 主动排除的表层特征

- 具体人物名（如宝玉、黛玉）
- 具体地名（如荣国府、大观园）
- 具体事件（如黛玉进贾府）
- 具体诗词和判词
- 固定句式（如“话说”“且说”）

## 来源与许可

| 来源 | 角色 | 许可 | SHA-256 |
|---|---|---|---|
| [《红楼梦》第一回](https://zh.wikisource.org/wiki/%E7%B4%85%E6%A8%93%E5%A4%A2/%E7%AC%AC001%E5%9B%9E) | training | Public Domain（公版） | `98b18a407d35` |
| [《红楼梦》第三回](https://zh.wikisource.org/wiki/%E7%B4%85%E6%A8%93%E5%A4%A2/%E7%AC%AC003%E5%9B%9E) | training | Public Domain（公版） | `fa757209d029` |
| [《红楼梦》第五回](https://zh.wikisource.org/wiki/%E7%B4%85%E6%A8%93%E5%A4%A2/%E7%AC%AC005%E5%9B%9E) | training | Public Domain（公版） | `3f3ad46addc6` |
| [《红楼梦》第七回（留出）](https://zh.wikisource.org/wiki/%E7%B4%85%E6%A8%93%E5%A4%A2/%E7%AC%AC007%E5%9B%9E) | style_holdout | Public Domain（公版） | `097c5af458a0` |

完整机器可读记录：[`../../results/benchmark.json`](../../results/benchmark.json)
