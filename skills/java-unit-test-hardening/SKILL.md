---
name: java-unit-test-hardening
description: "为既有 Java/Maven 仓库按核心业务流建立可持续的行为测试安全网，覆盖 JUnit、Mockito、MyBatis、Testcontainers、缺陷刻画、批次状态与可复验证据。仅在用户显式调用 `$java-unit-test-hardening` 或明确点名本 skill 时使用；不要从普通单测、覆盖率、缺陷、重构、QA 或功能开发请求中自动触发。"
compatibility: "需要 Python 3.10+、Git 与提供 fcntl 的 POSIX 环境（macOS/Linux）；Maven、JDK、Docker 和数据库导出客户端按目标仓库与所选测试层需要。"
metadata:
  invocation: explicit-only
---

# Java 存量单元测试加固

## 只接受显式调用

只有用户直接点名 `$java-unit-test-hardening` 或 `java-unit-test-hardening` 时才运行。若 skill 被意外加载，停止执行，不读取目标代码，也不改动仓库。

本 skill 面向已经存在的 Java/Maven 服务，为缺少可靠测试的存量行为建立长期安全网。它不是新功能的普通 TDD 流程，也不以用例数或覆盖率数字代替业务行为验证。

## 固定安全边界

1. **一次只处理一个目标 Git 仓库。** 用户必须给出或确认精确仓库根目录。仓库应包含根 `pom.xml`；多模块仓库在 service campaign 中逐模块盘点。
2. **从专用且完全干净的 worktree 启动。** tracked、untracked、冲突或未结束 Git 操作都会阻断入口。不要 stash、清理、覆盖或替用户分类现有修改。
3. **生产代码默认只记录、不修复。** 首次写入前在 `PRD.md` 固定 `production-fix-policy: record-only-confirmed`。默认可写范围只有测试源码、测试资源、测试作用域依赖与构建配置、campaign 产物和 `docs/tests/` 证据。
4. **生产修复必须精确授权。** 只有用户主动指出当前 campaign 的本地 ticket 和具体修复类型，才能改为 `authorized-ticket-scoped`。普通的“继续”“确认”或 workflow 选择不构成授权。
5. **禁止修改真实 schema、运行配置、部署配置和生产作用域依赖。** schema 只能来自目标仓库内已跟踪且干净的快照或完整迁移链；只读导出需要单独授权，且不得执行 DDL。
6. **外部与 Git 持久化动作分别授权。** clone、branch/worktree 创建、commit、push、PR/MR、远程 issue 和 schema 导出都不由 skill 调用或批次选择自动授权。
7. **不得制造绿色结果。** 不降低门禁，不因 Docker 缺失跳过必需集成测试，不修改旧断言迎合疑似缺陷，不靠反复运行等待 flaky 偶然通过。
8. **一个写域只有一个 writer。** 默认使用 `sequential`。只有用户授权且不同 workflow 的 module、worktree 与 `test_build_files` 全部互斥时，才使用 `parallel`。

`record-only-confirmed` 下的已确认缺陷必须同时保留：

- 一个启用的 characterization test，用来锁定当前真实行为；
- 一个本地 ticket，写清期望行为、影响和精确 `TestClass#method` 证据。

不要预先创建禁用的未来回归测试。只有生产修复获得授权后，才新增或改写为启用的 expected-behavior regression test。

## 使用 bundled 资源

先确定当前 `SKILL.md` 所在目录，并把它作为 `<skill-root>`。所有脚本、模板和引用都从该目录解析，不假设 skill 安装在 `.codex/skills`、`.agents/skills` 或任何固定用户路径。

执行前完整读取 `references/maven-test-policy.md`。需要创建产物时，从 `assets/templates/` 复制对应模板并替换全部占位符；保留机器字段名，面向人的标题和正文使用用户当前语言。

## 入口预检

### 1. 锁定仓库与外部 campaign 工作区

campaign 的事实台账位于：

```text
<campaign-workspace>/.scratch/<service-id>-test-campaign/BACKLOG.md
```

`<campaign-workspace>` 必须存在，并位于目标仓库之外。这样 campaign journal 不会成为被测仓库的未跟踪文件。`<service-id>` 使用稳定的 ASCII 标识；默认取仓库目录名，不合法时由用户明确提供。

### 2. 运行只读预检

```bash
python3 "<skill-root>/scripts/preflight.py" \
  --repository-root "<target-repository>" \
  --campaign-workspace "<external-workspace>" \
  --service-id "<stable-service-id>" \
  --service-campaign \
  --format json
```

关键结果：

- `READY`：继续；输出会绑定 real path、branch、HEAD、origin、Maven modules 和 campaign 路径。
- `WORKTREE_NOT_CLEAN`、`GIT_CONFLICT`、`GIT_OPERATION_IN_PROGRESS`：硬停止，由用户先处理现有状态。
- `REPOSITORY_NOT_ROOT`、`UNSUPPORTED_PROJECT`、`MAVEN_INVALID`：修正目标或仓库结构后重跑。
- `SERVICE_ID_REQUIRED`、`MODULE_SELECTION_REQUIRED`：展示候选值并等待用户选择。
- 其他 exit 3：硬停止，不得绕过。

预检只读：不创建 campaign、分支或 worktree，不安装工具，不初始化代码索引。

### 3. 读取仓库规范并建立代码证据

读取目标路径适用的 `AGENTS.md`/等价说明、README、根与模块 POM、测试约定和已有测试。若环境已提供 CodeGraph 或同类可靠代码图能力，优先用于入口、调用链和影响分析；否则使用针对性的 `rg`、Maven module 结构、Spring/MyBatis 注册点和精确源码读取建立证据。不要把某个外部索引工具设为公共 skill 的必需依赖，也不要无边界地读取整仓。

把使用的工具、命令、代码 baseline、证据路径和限制写入 `PLAN.md`。

## 盘点核心流并选择批次

1. 从 `CORE-FLOW-INVENTORY.md` 盘点 Controller/RPC、Listener/Consumer、Job/Scheduler、状态变更 Service 和行为型 Mapper SQL。
2. 每个核心入口映射到稳定 `workflow-id`；排除项写明具体非业务或不在范围内的证据。
3. 按资金、库存、权限、不可逆状态、并发、租户边界和历史事故排序。
4. 继续顺序固定为：`in-progress` → `refresh-needed` → 最高风险 `pending`。
5. HEAD 漂移时只把有调用链、文件或契约证据表明确受影响的终态项改为 `refresh-needed`。

行为矩阵决定测试范围，不设置通用 unit/integration 用例数量下限。每个测试应对应不同的输入分区、状态、顺序、持久化结果、租户边界、重试/重复条件或失败语义。

在一次交互中展示本波次全部候选 workflow，并等待结构化选择，例如 `select: 1,3`。每项展示 workflow、module、风险、依赖、integration lane、artifact/docs 路径和允许修改的 POM；不得静默追加 workflow。

确认后从 `BATCH-RUN.json` 生成：

```text
<campaign-workspace>/.scratch/<service-id>-test-campaign/batches/<batch-id>/BATCH-RUN.json
```

其中 `workspace_root` 等于 `<campaign-workspace>`，`repository_root` 等于目标仓库 real path。选择只授权测试加固写范围，不授权生产修复、schema 导出或 Git/外部动作。

## 执行批次

### 1. Seal 不可变选择

```bash
python3 "<skill-root>/scripts/batch_run.py" seal \
  --run-file "<BATCH-RUN.json>" \
  --format json
```

Seal 要求目标 worktree 仍然完全干净，并绑定 repository、branch、HEAD、Maven modules、inventory hash、生产修复策略、workflow scope 和 writer topology。选择变化时创建新批次，不原地重封。

### 2. 原子启动和转换状态

使用 `advance` 在同一文件锁内完成 live path audit、journal 记录和状态转换：

```bash
python3 "<skill-root>/scripts/batch_run.py" advance \
  --run-file "<BATCH-RUN.json>" \
  --workflow "<workflow-id>" \
  --to in-progress \
  --evidence "PLAN.md#red" \
  --actor "<writer>" \
  --at "<ISO-8601>" \
  --expected-revision "<revision>" \
  --format json
```

审计只允许已选择 module 的 `src/test/**`、该 workflow 的 `docs_path`、`docs/tests/TRIAGE.md` 和显式 `test_build_files`。生产源码、schema、CI、部署、运行配置与无关路径会阻断转换。

### 3. 执行快速 TDD 内循环

每个行为按 RED → GREEN → REFACTOR 推进。先运行最窄测试，再扩大范围：

```bash
./mvnw -pl <module> -am -Dtest=<TestClass>#<method> test
./mvnw -pl <module> -am -Dtest=<TestClass> test
```

只有在 workflow 检查点运行模块测试；只有收口时运行一次完整 Dockerless lane。需要真实数据库时用 Testcontainers 与 `-Dit.test=<ITClass>` 做窄内循环，最终只保留一次干净 integration lane 作为证据。内循环不运行 `clean`。

失败、flaky、容器或版本问题必须先定位根因。若当前环境存在系统化调试或完成前验证 skill，可显式使用；不存在时按同样纪律保留失败证据、最小复现和 fresh verification，不得假装已验证。

### 4. 选择正确测试层

- Service、Listener、Consumer：JUnit 5 + Mockito，优先直接构造被测对象；断言结果、异常、状态、事务决策和副作用顺序。
- Mapper SQL：使用与生产同数据库家族的 Testcontainers；断言谓词、影响行数、持久化状态、CAS、租户、逻辑删除、null/empty、重复 ID、分页和排序。
- Controller：只覆盖业务相关校验、授权、序列化和错误映射，不重复 Service 行为。

schema 来源依次为：仓库内已跟踪且干净的 `db/schema/`、权威完整迁移链、用户另行授权的 bundled `sync_schema.py` 只读导出。测试 DDL 从来源逐字提取相关表，不修改类型、默认值、字符集、排序规则或约束，不虚构字段。同步得到的快照若要持久化，必须走独立的 schema-baseline 维护，不属于当前 campaign。最终 `docs/tests/**` 只能引用同一目标仓库内已跟踪且干净的 schema；禁止主机绝对路径和兄弟仓库路径。

## 记录 finding 与 TRIAGE

每个 finding 立即写入 `issues/<ticket-id>-*.md`：

- `defect`：确认不变量被破坏；默认保留 characterization test 和 ticket。
- `suspected`：行为可疑但规则未确认；记录当前行为、决策 owner 和证据。
- `characterized`：反直觉但确认符合预期；只写矩阵和报告。
- `blind-spot`：无法覆盖的外部集成或不可达路径；逐项写入报告。
- `test-hygiene`：既有失败或不稳定测试；隔离前先建 ticket。

优先级固定派生：`confirmed+high=P0`、`confirmed+medium=P1`，其他有效组合为 `P2`。

```bash
python3 "<skill-root>/scripts/generate_triage.py" --root "<repository>/docs/tests"
python3 "<skill-root>/scripts/generate_triage.py" --root "<repository>/docs/tests" --check
```

## 收口 workflow

1. 运行一次完整 Dockerless lane；适用时运行一次干净 integration lane。
2. 若仓库已接入 p3c-pmd，要求 Blocker/Critical 为 0。
3. 执行 `git diff --check`，审计全部 tracked/untracked 路径。
4. `validate_campaign.py` 返回零。
5. 复制 `REPORT.md`、`BEHAVIOR-MATRIX.md` 和 `issues/` 到 workflow 的 `docs/tests/` 路径。
6. `generate_triage.py --check` 与 `validate_portable_artifacts.py` 通过。
7. 生成 `WORKFLOW-EVIDENCE.json`，绑定 fresh Surefire/Failsafe XML、campaign 目录、生产修复策略和复制产物 hash。
8. 用 `advance --to complete --evidence-manifest <WORKFLOW-EVIDENCE.json>` 原子收口。

剩余风险只有在用户明确接受具体 risk IDs 后，才能通过 `RESIDUAL-ACCEPTANCE.json` 和 `accept-residual` 收口；命令会在同一锁内重新审计。

## 收口 service campaign

service 完成要求：

- `inventory-status: complete`；
- 每个 module 的 discovered = mapped + excluded；
- 每条核心流映射到终态 workflow；
- 每个核心 workflow 为 `complete` 或明确的 `residual-accepted`；
- `SERVICE-REPORT.md` 与 BACKLOG 汇总一致；
- TRIAGE 和 portable evidence 校验通过。

```bash
python3 "<skill-root>/scripts/validate_service_campaign.py" \
  --workspace-root "<campaign-workspace>" \
  --campaign-root "<campaign-root>" \
  --format json
```

结果必须为 `VALID` 且 `closure_ready: true`。这只表示测试加固 campaign 已收口，不表示代码已提交、合并、部署或发布。
