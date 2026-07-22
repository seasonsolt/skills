# <Service Workflow> Behavior Matrix

<!-- Internal structure template. Localize all human-facing text before materializing it. -->

| Entry point | Scenario | Initial state/input | Expected observable result | Side effects/order | Test level | Evidence or ticket | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `<method>` | Happy path | <state> | <result> | <effects> | Unit | `<test>` | planned |
| `<method>` | Invalid state | <state> | <error/no-op> | None | Unit | `<test>` | planned |
| `<method>` | Duplicate call | <state> | <idempotent result> | No duplicate effect | Unit/IT | `<test>` | planned |
| `<mapper>` | Lost update | <concurrent state> | 0 affected rows | State preserved | Database IT | `<test>` | planned |
| `<mapper>` | Tenant boundary | <other tenant> | No visibility/update | State preserved | Database IT | `<test>` | planned |

Expected behavior must come from a confirmed invariant or decision, not from copying the current implementation. Any contradiction requires a linked ticket.

## Residual Risks

- <Untested behavior and reason>
