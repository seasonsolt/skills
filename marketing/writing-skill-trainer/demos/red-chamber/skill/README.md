[返回 《红楼梦》章回体续写 Demo](../README.md)

# Generated Skill Demo：《红楼梦》章回体续写

> 这是 DeepSeek 在 benchmark 中从 3 篇样本实际生成、并在训练后组实际加载的 Skill bundle。

## 文件

```text
skill/
├── README.md
├── SKILL.md
└── references/
    └── style-profile.md
```

- [`SKILL.md`](SKILL.md)：运行时流程、事实边界和自检。
- [`references/style-profile.md`](references/style-profile.md)：从样本提炼的机制、语气旋钮与反模式。

## 使用方式

将整个 `skill/` 目录复制到你的 Agent 支持的 Skill 目录，再按平台要求加载。不要只复制 `SKILL.md`，因为运行时会读取 `references/style-profile.md`。

> [!CAUTION]
> 这是实验候选版本，不代表已达到生产发布标准。请先检查触发描述、版权边界、事实约束和输出长度。

Run: `deepseek-launch-final-20260812` · requested model: `deepseek-chat` · actual model: `deepseek-v4-flash`
