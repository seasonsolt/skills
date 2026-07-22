# <Service Workflow> Test Hardening Report

<!-- Internal structure template. Localize all human-facing text before materializing it. -->

Status: complete

campaign-status: complete

Branch / baseline / verified commit: `<branch>` / `<baseline SHA>` / `<working tree or commit SHA>`

production-fix-policy: `record-only-confirmed`
authorized-fix-tickets: `none`

## Results

| Suite | Tests | Failures | Errors | Skipped |
| --- | ---: | ---: | ---: | ---: |
| Unit | <count> | 0 | 0 | <n> |
| Database integration | <count> | 0 | 0 | <n> |

每个跳过的测试必须关联一个本地问题单；一个问题单可以关联多个跳过测试。未解释的跳过会阻断收口。

## Coverage

| Scope | Lines | Branches | Notes |
| --- | ---: | ---: | --- |
| Module | <value> | <value> | Baseline: <value> |
| Target workflow | <value> | <value> | <selected classes/methods> |

Mapper XML coverage: <scenario summary; do not use JaCoCo percentage>

## Schema Evidence

- Source snapshot / hash / provenance: `<repository-relative or document-relative path, SHA-256, tracked-clean evidence>`
- Source-to-test drift check: `<command and result, or blocker>`
- Portable evidence validation: `<validate_portable_artifacts.py command and VALID result>`

## Findings

| # | Ticket | Priority | Verification / Severity | Type | Summary | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `issues/<n>` | P0 | confirmed / high | defect | <invariant and recorded evidence> | recorded |

Priority 由 verification+severity 派生:`confirmed+high=P0`、`confirmed+medium=P1`、`suspected 或 latent=P2`。
Verification: `confirmed`(生产代码已抽验) / `suspected`(需业务确认意图) / `latent`(未开票)。
Types: `defect`, `suspected` (name the pending decision owner), `characterized` (matrix row reference).

## Blind Spots

- <Deliberately stubbed or untested path and why, or "none">

## Verification

```bash
<Dockerless default command>
<Docker-capable integration command; or not applicable with evidence>
```

Do not report the integration lane as not applicable merely because Docker is unavailable. Prove that the repository has no integration profile or `*IT` source and that no in-scope matrix row needs integration coverage.

JaCoCo report: `<repository-relative path>`

## Diff Audit

- Allowed changed paths: `<paths>`
- Campaign 启动时工作区状态：`clean`
- Production source diff: `<none, or separately authorized ticket commits>`
- Schema/runtime config/deployment diff: `<must be none>`
- Test-gate CI diff: `<none, or explicitly authorized paths>`
- `git diff --check`: `<result>`

## Residual Risks

- <Remaining risk or none. A recorded defect under record-only-confirmed is an unresolved risk, not a pending authorization request or closure blocker.>
