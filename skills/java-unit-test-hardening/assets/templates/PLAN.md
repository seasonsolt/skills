# <服务工作流> 行为测试计划

<!-- 内部结构模板。落盘前替换占位符并删除本注释。 -->

状态：in-progress

## 入口快照

- 服务 / 模块：`<service>` / `<module or root>`
- 仓库根目录：`<resolved root>`
- 分支 / baseline：`<branch>` / `<full SHA>`
- 入口工作区状态：`clean`
- 代码检索 / 调用链工具：`<available tools, commands and result>`
- 规范来源：`<AGENTS.md、README、POM、domain docs、JAVA-CODING-STANDARD.md>`
- 批次 / run file：`<batch-id>` / `<BATCH-RUN.json path>`
- writer：`<coordinator and writer binding>`
- workflow 顺序：`<workflow IDs and dependencies>`
- production-fix-policy-snapshot: `record-only-confirmed`
- authorized-fix-tickets-snapshot: `none`

## 行为范围

- 核心入口与调用链：`<tool/query and exact code evidence>`
- 必测行为维度：`<input/state/order/persistence/tenant/retry/failure dimensions>`
- Integration lane：`<required or not-applicable with evidence>`
- 允许修改的测试构建文件：`<POM paths or none>`

## 执行计划

| 阶段 | 状态 | 产物 |
| --- | --- | --- |
| 调用链与行为矩阵 | pending | `BEHAVIOR-MATRIX.md` |
| 最窄 RED/GREEN 内循环 | pending | JUnit/Mockito/MyBatis tests |
| 模块级验证 | pending | Surefire/Failsafe XML |
| Findings | pending | `issues/` |
| 证据发布与收口 | pending | `REPORT.md`、`docs/tests/` |

## Schema 来源

- 仓库内来源：`<db/schema path or migration root>`
- Git 状态 / provenance：`<tracked-clean evidence>`
- 内容 hash：`<algorithm:value>`
- 测试 DDL：`<test resource paths>`
- 最后 drift check：`<date, command, result>`

## 完成条件

- 每个高风险矩阵项有测试或明确接受的剩余风险。
- 最终 Dockerless lane 通过；适用时 integration lane 通过。
- 所有跳过测试都有具体原因和 ticket。
- 没有 schema、生产配置、部署文件或无关用户文件进入 diff。
- `validate_campaign.py`、TRIAGE freshness 和 portable evidence 均通过。

## 续跑说明

<精确记录下一阶段、文件、阻塞事实和命令；不得写泛化的“继续”。record-only-confirmed 下不得把生产修复授权写成待办或阻塞项。>
