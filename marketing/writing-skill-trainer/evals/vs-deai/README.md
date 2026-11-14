[返回 Writing Skill Trainer](../../README.md)

# 对照评测：训练出的 Writing Skill 对比两个去 AI 味 skill

**结论：三个场景里赢了两个，输了一个。** 用 trainer 从 3 篇样本训练出的 skill，在中性科技新闻和英文幽默随笔上，口吻最接近目标作者，综合也排第一；在鲁迅式讽刺短篇上，口吻排在最后，stop-slop 排第一。humanizer-zh 改写后的稿件和原稿几乎一样，口吻名次也和原稿接近。

这次评测用的 skill 是 v1：只做了取证和起草，没有跑 trainer 的进化轮。

## 比的是什么

同一个任务，同一个生成模型，五种做法：

| 条件 | 做法 |
|---|---|
| `direct` | 不加载任何 skill，直接写 |
| `stopslop` | 写作时加载 [stop-slop](https://github.com/hardikpandya/stop-slop)（commit `8da1f03`，MIT，约 1.9 万星） |
| `humanizer` | 用 [humanizer-zh](https://github.com/op7418/dsh-guizang-design/tree/main/skills/humanizer-zh)（commit `e275f1e`，skill 目录 MIT）润色 `direct` 的稿件 |
| `humanizer-samples` | 同上，另外把 3 篇训练样本交给它当作者样本（它的规则写明“有样本时借鉴”） |
| `trained` | 加载 trainer 从同样 3 篇样本训练出的 skill 后写 |

两个去 AI 味 skill 都按它们文档写的用法来用。stop-slop 是英文 skill，中文任务上让它“能迁移的规则就用”；humanizer-zh 是中文 skill，英文任务上同样处理。跨语言的格子在下面的表里用 † 标出。

三个场景，每个场景 3 篇训练样本加 1 篇留出样本（写稿的一方都看不到，只给评审）：

| 场景 | 样本来源 | 任务 |
|---|---|---|
| `restrained-satire` | 鲁迅《孔乙己》《一件小事》《故乡》，留出《药》（公版） | 把一段虚构素材写成 800—1100 字的现代讽刺短篇 |
| `tech-news` | 中文维基新闻 3 篇，留出 1 篇（CC BY 2.5） | 按虚构事实包写 450—650 字的科技新闻，不得补造 |
| `twain-essay` | Mark Twain 随笔 3 篇，留出 *How to Tell a Story*（公版） | 按虚构素材写 450—650 词的英文幽默随笔，不得补造 |

## 结果

每个格子是 2 份样本 × 3 名评审，共 6 次评审。名次 1 最好，5 最差。“事实违规稿”指 2 份稿件里，有几份被至少 2 名评审判为违反任务自己的事实约束。

### 口吻：离留出样本的作者有多近（平均名次，括号里是排第一的次数）

| 条件 | 科技新闻 | 英文随笔 | 讽刺短篇 |
|---|---:|---:|---:|
| `direct` | 3.17 (0) | 2.33 (0) | 3.33 (0) |
| `stopslop` | 4.33 (0) † | 5.00 (0) | **1.00 (6)** † |
| `humanizer` | 3.00 (1) | 3.67 (0) † | 2.83 (0) |
| `humanizer-samples` | 2.83 (1) | 3.00 (0) † | 2.83 (0) |
| `trained` | **1.67 (4)** | **1.00 (6)** | 5.00 (0) |

### 综合：评审认为该发哪一份（平均名次，括号里是排第一的次数）

| 条件 | 科技新闻 | 英文随笔 | 讽刺短篇 |
|---|---:|---:|---:|
| `direct` | 2.83 (0) | 2.67 (0) | 3.83 (0) |
| `stopslop` | 4.00 (0) † | 5.00 (0) | **1.50 (3)** † |
| `humanizer` | 2.50 (1) | 3.83 (0) † | 3.33 (0) |
| `humanizer-samples` | 4.50 (0) | 2.33 (1) † | 3.33 (0) |
| `trained` | **1.17 (5)** | **1.17 (5)** | 3.00 (3) |

### 事实违规稿（2 份里有几份）

| 条件 | 科技新闻 | 英文随笔 | 讽刺短篇 |
|---|---:|---:|---:|
| `direct` | 2 | 2 | 1 |
| `stopslop` | 2 | 2 | 1 |
| `humanizer` | 1 | 2 | 1 |
| `humanizer-samples` | 2 | 2 | 1 |
| `trained` | **0** | 2 | **0** |

原始数据在 [`results.json`](results.json)，逐评审的结论在 `work/judge/*/verdicts.json`。

## 怎么读这些数字

**1. 赢的两个场景，差距来自“知道要学谁”。** 科技新闻里，评审的理由是训练后的稿件有电头、导语密、每个说法都带出处、不做推断；其他几份多半在结尾加了一句素材里没有的推测。英文随笔里，训练后的稿件 6 次评审都排口吻第一，stop-slop 6 次都排最后。评审的说法是：前者一本正经地讲、把包袱随手带过，后者用现代的短句抖包袱。英文是 stop-slop 的主场，它删掉的是套话，但不知道目标作者怎么写。

**2. 输的一个场景，原因在训练出的 skill 自己。** 讽刺短篇里，训练后的稿件 6 次评审都排口吻最后。评审的理由一致：它不停地替读者解释讽刺（如“名字取得很准”），而留出样本是让具体的物件和动作自己说话。stop-slop 的稿件补了不少素材里没有的细节（信的内容、保安、鞋摊不见了），读起来反而更接近。我们给这个 skill 定的契约是“不新增素材外的人物和事件”，这条对小说任务过严：细节不能补，叙述者就只能靠评论填字数。这是 v1 没跑进化轮就拿来比的结果，我们没有改了再测。

**3. 事实约束是训练后稿件最稳的一项，但不是全胜。** 科技新闻里，只有训练后的 2 份稿件都没有被判违规，其余条件各有 1—2 份被判（补推测、把“三所高校和 12 家企业”合计成“15 家”等）。讽刺短篇里，另外四个条件的第 2 份稿件都把“下班前替老人选了已了解”挪到了下午当着老人的面，训练后的稿件没有。英文随笔里，五个条件的稿件全部被判补了素材外的内容，训练后的稿件也在内，只是补得最少（如把打热线的时间写成“第三天”）。

**4. humanizer-zh 几乎没有改动稿件。** 不给样本时，改写稿和原稿的相似度是 0.94—1.00；给了样本是 0.86—0.97。它的规则写明要保留事实、没问题的段落原样保留，它做到了，所以口吻名次也跟原稿差不多。它是润色工具，不负责把稿件改成某个作者的写法。

**5. 按去 AI 味 skill 自己的清单数，中文稿件里本来就没有可删的东西。** [`tells.py`](tells.py) 用两个 skill 的禁用清单写了一组正则。两个中文场景里，五个条件（包括什么都不加载的 `direct`）全部是 0 处。英文随笔里，`direct` 每千词 1.6—3.4 处，`stopslop` 是 1.9 和 0，`trained` 是 0。正则很粗，只能当密度参考。

## 这说明什么，不说明什么

去 AI 味 skill 和 trainer 做的不是同一件事。前者是一份固定的“不要这样写”清单，对谁都一样；后者从你的样本里学“你怎么写”，并带着事实约束。这次评测里，前者没有让稿件更接近目标作者（讽刺短篇除外），后者在三个场景里做到了两个。

不能据此说 trainer 在所有文体上都更好。讽刺短篇就是反例，而且输得很整齐。

## 局限

- 每个场景只有 1 个任务、2 份样本，6 次评审。样本量小，只能看方向。
- 生成用 Claude Sonnet，评审用 Claude Opus，是同一家的模型；评审不是人。评审可能偏爱某种写法。
- 口吻只对照 1 篇留出样本。
- 训练出的 skill 是 v1，没有经过 trainer 的盲评进化轮；三个 skill 的契约都由同一份任务说明规定了“不新增素材外事实”。
- stop-slop 用在中文、humanizer-zh 用在英文，都超出了它们的设计范围（表里的 †）。
- 多份稿件彼此几乎相同（humanizer-zh 的改写稿和原稿），它们之间的名次接近随机。
- 没有比“只把样本贴进提示词、不训练 skill”这种做法；`humanizer-samples` 最接近它，但不等同。

## 复现

```bash
# 1. 场景文件（英文样本需要先下载 Project Gutenberg #2572、#3250 的纯文本，
#    以及 en.wikisource 上 Taming the Bicycle、The Danger of Lying in Bed 的 extract JSON）
python3 -I build_scenarios.py <下载目录>

# 2. 按 gen-prompts.md 生成 work/out/<条件>-<1|2>/<场景>.md

# 3. 机械检查、痕迹计数、盲评材料、汇总
python3 -I ../../../../skills/writing-skill-trainer/scripts/precheck.py \
    --prompts prompts.json work/out/*/ > work/precheck.jsonl
python3 -I tells.py work/out > work/tells.jsonl
python3 -I prep_judge.py          # 生成 work/judge/ 和 work/judge-secret/mapping.json
#    按 judge-prompt.md 跑 6 个评审
python3 -I aggregate.py           # 写 results.json
```

- 生成和评审的提示词：[`gen-prompts.md`](gen-prompts.md)、[`judge-prompt.md`](judge-prompt.md)
- 训练出的三个 skill 和取证台账：`work/<场景>/skill/`
- 全部 30 份稿件：`work/out/`
- 机械检查：30 份稿件字数全部在范围内；只有 `stopslop-1` 的科技新闻出现了素材外的数字“15”（[`work/precheck.jsonl`](work/precheck.jsonl)）

运行日期：2026-11-14。
