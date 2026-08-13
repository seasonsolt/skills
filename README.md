# Seasonsolt Skills

一组**可验证、边界清晰、可移植**的 Agent Skills，覆盖内容创作、知识工作与软件工程。每个 skill 都把触发条件、工作流、依赖与安全边界放在自己的目录里；有测试或实验的能力同时保留可复查证据。

> **English summary:** A curated collection of verifiable, boundary-aware, portable agent skills for creation, knowledge work, and software engineering. Chinese is the canonical documentation language; contributions and issue reports in English are welcome.

## 为什么是这个仓库

- **可验证**：脚本型 skill 提供可运行测试；Writing Skill Trainer 公开完整 A/B 实验、原始结果与失败案例。
- **边界清晰**：涉及授权、隐私、生产修改、账号操作或外部系统时，skill 会说明允许范围与停止条件。
- **可移植**：skill 从自身目录解析 `scripts/`、`references/` 和 `assets/`，不依赖维护者机器上的固定路径。

## Skill 目录

`First-party` 表示以本仓为维护源；`Vendored` 表示保留上游来源和独立许可证的第三方内容。当前没有标为 Stable 的 skill。

### Create

| Skill | 用途 | 来源 | 成熟度 |
|---|---|---|---|
| [`writing-skill-trainer`](skills/writing-skill-trainer/) | 从授权写作样本提炼、盲评并迭代可复用 Writing Skill | First-party | Beta |
| [`xiaohongshu-content`](skills/xiaohongshu-content/) | 小红书诊断、定位、选题、文案、配图、草稿与发布流程 | First-party | Preview |
| [`humanizer-zh`](skills/humanizer-zh/) | 识别 24 类中文 AI 写作痕迹并自然改写 | Vendored | Upstream |

### Work

| Skill | 用途 | 来源 | 成熟度 |
|---|---|---|---|
| [`write-daily-report`](skills/write-daily-report/) | 从用户材料或获准目录内的 Codex、Claude Code、Pi Agent 会话生成日报 | First-party | Beta |

### Engineer

| Skill | 用途 | 来源 | 成熟度 |
|---|---|---|---|
| [`java-unit-test-hardening`](skills/java-unit-test-hardening/) | 为既有 Java/Maven 服务建立行为测试安全网与可复验证据 | First-party | Beta |
| [`build-domain-wiki`](skills/build-domain-wiki/) | 建立有证据、分层深度和质量门禁的 DDD 领域知识库 | First-party | Preview |

`build-domain-wiki` 与 `java-unit-test-hardening` 只接受显式调用。后者要求 Python 3.10+、Git 和 macOS/Linux；Maven、JDK、Docker 与数据库工具按目标测试层需要。

`write-daily-report` 的本地会话采集只读取用户批准的工作范围。其脚本接受可重复的 `--work-root`，也支持用操作系统路径分隔符设置 `DAILY_REPORT_WORK_ROOTS`。

## 真实验证证据

[`writing-skill-trainer` 对照实验](marketing/writing-skill-trainer/)在同一模型、同一任务参数下比较直接生成与加载训练后 Skill：匿名质量偏好为 **7/9 对 2/9**，连续来源重合警报为 **0/18**。加入长度、事实和复制硬约束后，训练后胜 3、直接胜 2、双方均未通过 4；仓库保留失败结果、固定代表稿、原始 JSON、来源许可与复现脚本，不把偏好分数包装成最终通过率。

## 在 Codex 中手动安装

Codex 的当前约定是：个人通用 skills 放在 `~/.agents/skills`，项目共享 skills 放在仓库的 `.agents/skills`；一个 skill 目录至少包含 `SKILL.md`，也可以带 `scripts/`、`references/` 和 `assets/`。官方同时建议把跨团队发行的 skills 包装成 plugin。参见 [Build skills](https://learn.chatgpt.com/docs/build-skills) 与 [Plugin packaging](https://developers.openai.com/plugins/build/plugins)。

本仓包含最小 plugin manifest，但目前没有发布 Marketplace 安装源，也不提供一键 installer。下面的复制步骤是可审计的最小安装方式。

安装单个 skill 到个人目录：

```bash
git clone --depth 1 https://github.com/seasonsolt/skills.git seasonsolt-skills
mkdir -p ~/.agents/skills
cp -R seasonsolt-skills/skills/writing-skill-trainer ~/.agents/skills/
test -f ~/.agents/skills/writing-skill-trainer/SKILL.md
```

只对当前项目启用时，将目标目录复制进该项目：

```bash
mkdir -p .agents/skills
cp -R /absolute/path/to/seasonsolt-skills/skills/write-daily-report .agents/skills/
test -f .agents/skills/write-daily-report/SKILL.md
```

复制整个 skill 目录，不要只复制 `SKILL.md`，否则它引用的脚本、参考资料和模板会缺失。Codex 会自动发现变更；若 skill 没有出现，再重启 Codex。

## 兼容性

| 使用方式 | 状态 | 说明 |
|---|---|---|
| Codex plugin / `.agents/skills` | 已验证元数据与目录结构 | 6 个 skill 均带 `agents/openai.yaml`；仓库检查固定使用 Python 3.10。 |
| Claude Code | 预期可手动使用，未纳入 CI | 部分 skill 保留 Claude 风格指令；安装位置和工具名按客户端约定调整。 |
| 其他支持 `SKILL.md` 的 agent | 预期可移植，未逐一验证 | 复制完整目录并先检查工具、网络、路径与外部动作语义。 |

## 调用与验证

显式调用最可预测：

```text
$writing-skill-trainer 请从这些已获授权的文章中提炼一个 Writing Skill，并做盲评验证。
$write-daily-report 请只扫描 /path/to/approved/work-root，生成今天的日报。
$java-unit-test-hardening 请为 /path/to/clean-maven-worktree 建立测试加固计划。
```

除两个 explicit-only skills 外，Codex 也可能在请求与 `description` 匹配时自动选择 skill。首次使用建议显式点名，并确认 Codex 已读取目标目录中的 `SKILL.md`；涉及脚本时，再运行该 skill 文档列出的最小测试或预检命令。

仓库维护者在提交前运行：

```bash
# 快速检查元数据、JSON、链接与脚本语法
python3 scripts/check.py --quick

# 完整检查（另需 PyYAML、pytest 和 Ruby）
python3 scripts/check.py
```

统一检查要求 Python 3.10+；CI 固定使用 Python 3.10。提交时保留实际命令和结果，详细要求见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

## 安全、隐私与贡献

- 不要提交 API key、Cookie、会话正文、客户数据、账号资料、未公开草稿或维护者机器的私有绝对路径。
- 小红书 `posts/` 是使用者私有归档，不属于公开仓内容。
- 贡献新 skill 时必须说明来源、许可证、触发与非触发条件、外部依赖、写入范围和验证证据。

参与方式见 [`CONTRIBUTING.md`](CONTRIBUTING.md)；安全问题请按 [`SECURITY.md`](SECURITY.md) 私下报告；来源和例外见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。

## 许可证状态

**根许可证仍待维护者确认。** 在根 `LICENSE` 落地前，请不要把仓库中未带独立许可证的内容视为已经获得通用的复制、修改或再分发授权。

例外包括 [`humanizer-zh`](skills/humanizer-zh/LICENSE) 与 [`xiaohongshu-content`](skills/xiaohongshu-content/LICENSE) 各自许可证覆盖的 MIT 内容，以及 benchmark 中分别按 Public Domain、CC BY 2.5 使用的来源材料。完整范围、归属和待确认项记录在 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。
