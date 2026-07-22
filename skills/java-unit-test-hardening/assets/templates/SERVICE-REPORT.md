# <Service> Test Hardening Service Report

<!-- Materialize only after every core workflow is terminal. Localize human-facing text and remove this comment. -->

service-campaign-status: complete <!-- complete | residual-accepted -->
core-workflows-total: <count>
core-workflows-complete: <count>
core-workflows-residual-accepted: <count>

Inventory head / verified repository state: `<full SHA>` / `<working tree or commit evidence>`

## Module and Workflow Results

| module | core workflows | complete | residual-accepted | unit cases | integration cases | evidence |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| <module> | <count> | <count> | <count> | <count> | <count> | <links> |

## Core Entry Coverage

- Inventory reconciliation: `<all modules complete and counts reconciled>`
- Unmapped core entries: `none`
- Refresh-needed workflows: `none`
- 每条核心流均映射到已完成或明确接受剩余风险的 workflow
- 覆盖率仅作为报告证据，不按类长度设置额外完成门禁

## Residual Risks

按优先级汇总(每张 ticket 的 `priority` 派生自 `verification`+`severity`;P0 建议立即修、P1 排期、P2 先与业务确认意图):

| 优先级 | 条数 | ticket 编号(跨工作流) |
| --- | ---: | --- |
| P0（confirmed+high） | <count> | `issues/<...>` |
| P1（confirmed+medium） | <count> | `issues/<...>` |
| P2（suspected/latent） | <count> | `issues/<...>` |

- <其余聚合的 ticket 关联风险,或 none>

## Verification

```bash
python3 "<skill-root>/scripts/validate_service_campaign.py" --workspace-root "<campaign-workspace>" --campaign-root "<campaign-root>" --format json
```

Validator result: `VALID`, `closure_ready: true`.
