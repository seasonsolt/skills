# <Service> Test Hardening Campaign

<!-- Internal structure template. Localize human-facing text before materializing it; preserve machine keys and table column identifiers. -->

service-campaign-status: in-progress <!-- in-progress | complete | residual-accepted -->
core-inventory-status: partial <!-- partial | complete -->
completion-policy: all-core-workflows
service-baseline: <full Git SHA>
repository-root: <absolute target repository real path; internal campaign identity binding only>
active-batch-id: none
active-batch-run: none
active-batch-status: none

Repository root: `<resolved real path>`
Campaign workspace: `<external workspace real path>`

## Stop Condition

Pause only at a reproducible workflow boundary. Context or user budget may pause a run, but the service remains `in-progress` until all core workflows are terminal.

## Workflow Backlog

| workflow-id | module-id | core | priority | workflow | status | effort | branch | parent-branch | baseline | artifact-dir | evidence | findings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| <stable-id> | <module-id> | yes | P0 | <workflow> | pending | — | — | — | — | none | — | — |

Statuses: `pending`, `in-progress`, `complete`, `refresh-needed`, `residual-accepted`. Core flags: `yes`, `no`.

`Branch` follows `ut-<yyyymmdd>-<baseline-short-sha>[-<workflow>]`. `Baseline` is the target repository commit the row's status was earned against. On every invocation, map changes since that baseline back to inventory flows with available code-intelligence evidence; only affected terminal rows become `refresh-needed`.

## Module Coverage Trend

| date | module-id | lines | branches | terminal-core-workflows | total-core-workflows |
| --- | --- | --- | --- | ---: | ---: |
| <date> | <module-id> | <baseline> | <baseline> | 0 | <count> |

## Resume Instructions

<Exact active batch, next module, workflow, and phase; blockers, decisions, files, and commands needed to resume. Never recommend another service while a core row is non-terminal.>
