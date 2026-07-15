# Domain wiki output contract

## Default layout

Use this structure unless the user or repository already defines a compatible alternative:

```text
wiki/domain/
├── README.md
├── SUBDOMAIN-MAP.md
├── CONTEXT-MAP.md
├── SUBDOMAIN-CONTEXT-MAPPING.md
├── TERM-INDEX.md
├── FIRST-PASS-REVIEW.md
├── coverage/
│   ├── COVERAGE-LEDGER.md
│   ├── DISCOVERY-SURFACE.md
│   ├── REPOSITORY-BASELINE.md
│   ├── EVIDENCE-GAPS.md
│   ├── EVENT-DRIVEN-EVIDENCE.md
│   └── LONG-TAIL-CAPABILITIES.md
├── governance/
│   ├── KNOWLEDGE-STATUS.md
│   ├── QUALITY-GATES.md
│   ├── QUALITY-REPORT.md
│   └── REVIEW-REMEDIATION.md
├── subdomains/<slug>/README.md
└── contexts/<slug>/
    ├── README.md
    ├── CONTEXT.md
    ├── scenarios/<scenario>.md
    └── evidence/current-implementation.md
```

Create optional cross-cutting baselines only when evidence requires them, such as a MyBatis-Plus data-path baseline or an external-contract catalog.

`DISCOVERY-SURFACE.md` is the coverage denominator. For every repository or declared source, record whether frontends/routes, APIs, jobs, messages, SQL/migrations, configuration, external contracts, and runtime evidence were checked, excluded, missing, or not authorized.

## Required homepage metadata

Every subdomain and bounded-context `README.md` must declare:

```text
knowledge_status:
domain_owner:
maintainers:
last_reviewed:
coverage:
open_questions:
```

Use explicit unknown values such as `待指定`, `未复核`, or `无`, rather than deleting fields.

## Subdomain baseline

Each subdomain page must answer:

1. What business problem it solves.
2. Who receives value and what outcome matters.
3. Which capabilities belong to the problem space.
4. Which terms are central.
5. Which commands or decisions occur.
6. Which event semantics matter.
7. Which other problem areas it depends on.
8. What remains unknown and who should confirm it.

Do not define stable scenario or event identifiers at this layer.

## Bounded-context baseline

Each context homepage must state:

- purpose and model boundary;
- actors and responsibilities;
- owned language and non-owned concepts;
- rules and invariants;
- aggregate or consistency-boundary candidates;
- commands, scenarios, events, and policies;
- upstream/downstream relationships and translation needs;
- implementation evidence links;
- boundary counterevidence and open questions.

Treat aggregates and relationships as candidates until evidence and business confirmation support them.

## Glossary contract

`CONTEXT.md` contains only context-local domain terms:

```markdown
# <Context> ubiquitous language

## <Canonical term>

Definition in business language.

- Distinguish from: ...
- Allowed states: ...
- Open semantic question: ...
```

Exclude file paths, services, tables, APIs, framework names, queues, caches, deployment details, and code snippets.

## Scenario contract

Use stable context-owned identifiers:

```markdown
## `SCN-ORD-001` Submit order

1. Actor issues a command with required business information.
2. Context evaluates explicit rules and invariants.
3. Context changes business state or rejects the command.
4. Context emits an event candidate.
5. A downstream policy produces the business result.

## Event candidates

- `EVT-ORD-001 Order submitted`
```

Keep current behavior and target behavior visibly separate when they differ.

## Evidence contract

Each deep-context evidence page declares:

```text
knowledge_status:
evidence_status:
evidence_coverage:
code_baseline:
```

Recommended sections:

- observed behavior;
- Mapper/custom SQL and database observations;
- time/event-driven state changes;
- boundary evidence and competing hypotheses;
- risks and contradictions;
- exact evidence files;
- remaining runtime and business questions.

## Stable identifier ownership

| Prefix | Meaning | Definition owner |
| --- | --- | --- |
| `CAP-*` | Business capability | Coverage ledger |
| `Q-*` | Open question | One owning document |
| `RULE-*` | Domain rule candidate | Bounded context |
| `SCN-*` | Scenario | Bounded-context scenario document |
| `EVT-*` | Domain-event candidate | Bounded-context scenario document |

References may appear anywhere, but definitions must be unique.

## Status vocabulary

Knowledge status answers whether business meaning is confirmed:

- `探索中`
- `待业务确认`
- `部分确认`
- `已确认`

Evidence status answers what supports an observation:

- `静态已核验`
- `测试已验证`
- `运行已验证`
- `业务已确认`

Evidence coverage answers whether the relevant path is complete:

- `部分观察`
- `路径闭环`

Never infer `已确认` from code, tests, or developer agreement.
