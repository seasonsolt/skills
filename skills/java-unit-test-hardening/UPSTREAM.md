# 来源与公共化说明

本 skill 提取自 [`xjjk/ai-workspace` 的 `feature-20260714-ut-hardening-entry` 分支](https://cnb.cool/xjjk/ai-workspace/-/tree/feature-20260714-ut-hardening-entry)：

- 来源 commit：`eda5687bff1a5b2199a14fc59a643897e9741142`
- 来源路径：`.codex/skills/dev-service-unit-test-harden-from-backlog/`
- 来源 commit 作者：`zhangxun <zhangxun@xjjk.com>`

公共版本保留原始 campaign journal、写域边界、生产修复授权、Maven 测试策略、schema 来源约束、缺陷刻画和证据校验，并做了以下适配：

- skill 名称改为 `java-unit-test-hardening`；
- 目标由 ai-workspace 的 `services/<service>` 挂载改为用户显式指定的任意 Java/Maven Git 仓库；
- campaign 工作区必须位于目标仓库之外；
- 移除 `WORKFLOW-CONFIG.yaml`、`REPOSITORIES.yaml`、TAPD 与 OpenSpec 依赖；
- CodeGraph 从硬依赖改为“环境可用时优先”的代码证据增强能力；
- bundled 脚本使用 `<skill-root>` 解析，不绑定 `.codex/skills` 安装位置；
- 入口预检只依赖 Python 标准库与 Git。
