# <服务工作流> 行为测试需求说明

<!-- 内部结构模板。落盘前替换所有占位符并删除模板注释。 -->

状态：draft

campaign-status: draft <!-- draft | in-progress | complete | residual-accepted -->
ticket-evidence-version: 1

## 目标

<业务结果与安全不变量>

## 范围

- <入口与业务工作流>
- <Service、Listener、Consumer 与 Mapper XML 边界>

## 不在范围内

- <明确排除项>

## 生产代码修复授权

production-fix-policy: record-only-confirmed <!-- record-only-confirmed | authorized-ticket-scoped -->
authorized-fix-tickets: none <!-- authorized-ticket-scoped 时填写 issues/<ticket-id>，多个值使用英文逗号分隔 -->

- 决策人 / 日期 / 来源：<默认策略及落盘日期，或使用人对本 campaign 的原始明确决定>
- 精确修复类型：无 <!-- authorized-ticket-scoped 时必填；不得只写“修复缺陷” -->
- 决策约束：`record-only-confirmed` 是持续有效的 campaign 决策；普通的“继续”“确认”“按建议执行”不得重新打开或扩大生产修复授权

## 持久化授权

- 工作分支：yes <!-- campaign 首次修改前必须建立 -->
- 本地提交：no <!-- 需要明确授权 -->
- 推送：no <!-- 需要明确选择启用 -->
- 合并请求：no <!-- 需要明确选择启用；目标：<默认分支> -->
- 远程问题发布：no <!-- 本技能默认只维护本地问题单 -->

## 质量要求

- JDK 与测试框架版本：<版本>
- Java 行覆盖率目标：<目标>
- Java 分支覆盖率目标：<目标>
- SQL 场景要求：<场景>
- 行为矩阵：<按业务风险列出必须覆盖的行为维度，不设置通用用例数量下限>
- 缺陷处理：已确认缺陷必须建立本地问题单和当前行为刻画测试；预期行为写入问题单，只有生产修复获授权后才新增启用的回归测试
- CI 文件修改：no <!-- 需要明确选择启用 -->

## 验收标准

- <行为矩阵完整>
- <默认测试通道通过；适用的集成测试通道通过，或已有不适用证据>
- <剩余风险已记录>
