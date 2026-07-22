# Skills

Reusable agent skills maintained by seasonsolt.

## Available skills

- [`build-domain-wiki`](skills/build-domain-wiki/): build and review a full-coverage, evidence-backed DDD domain wiki with graded depth and quality gates.
- [`xiaohongshu-content`](skills/xiaohongshu-content/): 小红书内容从数据诊断到发布的全流程方法论(诊断→定位→选题→文案→配图→草稿→发布),源自 danqing。
- [`humanizer-zh`](skills/humanizer-zh/): 中文文本去 AI 味(24 项 AI 痕迹 + 50 分 rubric),vendored from op7418/Humanizer-zh (MIT),保留原 LICENSE 与出处。
- [`write-daily-report`](skills/write-daily-report/): 从用户记录或批准工作目录内的 Codex、Claude Code 与 Pi Agent 会话生成可直接提交的高质量日报；不预设个人路径或职业。
- [`java-unit-test-hardening`](skills/java-unit-test-hardening/): 为既有 Java/Maven 仓库按核心业务流建立可持续的行为测试安全网，含批次 journal、边界审计、缺陷刻画和可复验证据。

`build-domain-wiki` and `java-unit-test-hardening` are intentionally manual-only. Invoke them explicitly as `$build-domain-wiki` / `$java-unit-test-hardening`, or ask the agent to use the skill by name.

For automatic local-session collection, `write-daily-report` accepts repeatable `--work-root` arguments. Its helper scripts can also read multiple roots from `DAILY_REPORT_WORK_ROOTS` using the operating system's path separator.

`java-unit-test-hardening` runs against a user-selected clean Git worktree and stores campaign state outside the target repository. Runtime helpers require Python 3.10+, Git, and macOS/Linux; generated project tests use the target repository's own Maven/JDK toolchain.
