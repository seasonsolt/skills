# <Finding Title>

<!-- Internal structure template. Localize all human-facing text before materializing it. -->

```text
status: open
finding-type: defect # defect | suspected | test-hygiene
verification: confirmed # confirmed(生产代码已抽验) | suspected(需业务确认意图) | latent(已发现未开票)
severity: high # high(资金/逻辑硬伤/数据错误) | medium(NPE/一致性/幂等/静默丢失) | low(边角)
priority: P0 # 由 verification+severity 派生:confirmed+high=P0;confirmed+medium=P1;suspected 或 latent=P2
characterization-tests: `<TestClass#method>` # 多个测试分别使用反引号并以英文逗号分隔
regression-tests: none # 仅在生产修复获授权后填写启用的回归测试
```

Lifecycle — defect: `open` → `confirmed` → `recorded`（record-only 模式保留当前行为刻画测试与未解决风险）或 `fixed-local` → `merged`（也可在说明理由后进入 `wont-fix`）。
Lifecycle — suspected: `open` → `confirmed-defect` (then continue as defect) or `confirmed-intentional` (record the decision and the decider, keep the characterization test).

## Invariant

<Business rule that must hold>

## Reproduction

1. <Initial state>
2. <Action or concurrent event>
3. <Observed result>

## Impact

<Money, inventory, state, tenant, retry, or operability impact>

## Evidence

- Production path: `<file:symbol>`
- Behavior-matrix row: `<entry/scenario>`
- Characterization test: `<与 characterization-tests 一致的测试及其层级>`
- Regression test: `<生产修复获授权后填写；否则为 none>`

## Decision / Authorization

- Decision owner and evidence: <who confirmed the invariant or intent, with source>
- Campaign production-fix policy: <record-only-confirmed or authorized-ticket-scoped>
- Production-fix authorization: <out of scope for this campaign, or exact user-authorized ticket, fix type, source, and date>

## Expected Behavior

<Required observable result>

## Resolution

<For record-only-confirmed: "Production fix is out of scope for the current campaign; retain as an unresolved risk." For authorized-ticket-scoped: minimal fix and verification. Do not ask to change the policy here.>

## Comments

<Schema, environment, ownership, or follow-up facts that affect resolution. In final docs/tests evidence, reference schema only through a document-relative Markdown link or repository-relative db/schema path; never use a host absolute path or sibling repository.>
