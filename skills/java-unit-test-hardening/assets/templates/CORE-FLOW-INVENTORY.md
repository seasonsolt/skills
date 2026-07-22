# <Service> Core Flow Inventory

<!-- Internal structure template. Localize human-facing text before materializing it; preserve machine keys and table column identifiers. -->

inventory-status: partial <!-- partial | complete -->
inventory-head: <full Git SHA used for the code inventory>

## Module Reconciliation

| module-id | module-path | scan-status | discovered-entry-count | mapped-entry-count | excluded-entry-count | evidence |
| --- | --- | --- | ---: | ---: | ---: | --- |
| <stable-module-id> | <repository-relative path> | partial | 0 | 0 | 0 | <tool/query and code evidence> |

For a completed module, `discovered-entry-count` must equal `mapped-entry-count + excluded-entry-count`. Every exclusion needs a concrete non-business or out-of-scope reason in the evidence.

## Core Flow Mapping

| flow-id | module-id | entry-symbols | workflow-id | core | evidence |
| --- | --- | --- | --- | --- | --- |
| <stable-flow-id> | <module-id> | <Controller/RPC/listener/job/service symbols> | <workflow-id> | yes | <call-path evidence and risk basis> |

Each core flow maps to exactly one backlog workflow. Related entry symbols may share a cohesive workflow; unrelated modules or business outcomes require separate rows.

## Explicit Exclusions

- <Entry symbol, reason, owner/evidence. Do not use package names or low coverage alone as an exclusion reason.>
