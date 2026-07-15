# Implementation evidence workflow

## Evidence principle

Use implementation to establish current observable behavior, not business legitimacy. Every important statement must reveal whether it is:

- business-confirmed fact;
- statically observed implementation;
- runtime-verified behavior;
- target-model candidate;
- inference or boundary hypothesis;
- unresolved question.

Record the repository commit and dirty state so conclusions remain reproducible.

Before runtime evidence collection, confirm explicit authority for the target environment, logs, credentials, and production-derived data. Minimize sensitive data and never copy secrets or personal data into the wiki. Without authority, stop at static evidence and label runtime behavior unverified.

## Code discovery sequence

When `.codegraph/` exists, ask CodeGraph about the symbol, scenario, and call path before using grep/find or manually opening many code files.

Trace each critical scenario through:

1. Actor-facing entry and caller identity.
2. Application/Service orchestration and transaction boundary.
3. Domain decisions, state checks, and exception paths.
4. Persistence interface and custom SQL.
5. Cache, Lua, search, document database, or other state stores.
6. Outbound RPC and third-party side effects.
7. Messages, consumers, tasks, callbacks, retries, and compensation.
8. Database constraints and atomic update conditions.
9. Runtime configuration that activates, skips, or reroutes behavior.

Do not stop at the happy synchronous path.

## MyBatis-Plus and XML systems

Inspect all of these before declaring a rule implemented:

- Service and ServiceImpl orchestration;
- Mapper interfaces;
- every relevant `mapper/*.xml` statement;
- annotation SQL;
- `QueryWrapper`, `UpdateWrapper`, and Lambda Wrapper predicates;
- tenant, logic-delete, pagination, and optimistic-lock interceptors;
- entity annotations such as table, version, tenant, and deleted fields;
- database primary keys, unique constraints, indexes, defaults, and nullability;
- batch updates and generic Mapper calls that bypass custom XML;
- jobs/listeners without request-thread tenant context.

Check whether updates contain the expected old state, version, tenant, deletion guard, idempotency key, and exact business identifier. A `version` column proves nothing if the critical SQL does not use it.

Centralize framework-wide observations in one baseline instead of repeating speculative warnings in every context.

## Time and event-driven paths

For each deep context, enumerate:

- message producers and consumers;
- topic/queue identity and event version when known;
- scheduled and delayed jobs;
- external callbacks/webhooks;
- workflow/process listeners;
- retry, dead-letter, replay, timeout, and reconciliation mechanisms;
- state changes performed by each entry;
- tenant-context setup and cleanup;
- idempotency key and expected-old-state condition.

File existence is only static discovery. Do not infer that a listener is subscribed, a task is scheduled, or the deployed artifact matches the source. Use `evidence_coverage: 部分观察` until those claims are verified.

## Distributed side effects

Identify operations outside the local transaction:

- RPC calls;
- MQ sends;
- external payment or channel calls;
- Redis counters/locks;
- search index writes;
- document database logs;
- third-party order, logistics, or communication systems.

Record ordering, partial success, retry semantics, compensation, and the business source of truth. A local `@Transactional` annotation cannot roll back these effects.

## State-machine evidence

For every state-changing path, capture:

- accepted old states;
- resulting state;
- actor or time/event trigger;
- guard and invariant;
- concurrent competing writers;
- terminal and recovery states;
- invalid or orphan states with no observed writer;
- direct SQL/Wrapper/job paths that bypass the nominal owner.

Do not combine current implementation states and target state semantics in one unlabeled diagram.

## Boundary counterevidence

Actively search for:

- multiple entities mapped to the same table;
- multiple services writing the same state;
- reverse calls that make ownership circular;
- shared identifiers without translation;
- database or cache keys missing context/tenant dimensions;
- generic wrappers that bypass declared invariants;
- one external contract used as the true authority across candidates.

Write these as evidence and competing hypotheses, not immediate reclassification.

## External business contracts

Include an external system only when it imposes business semantics such as payment, fulfillment, identity, communication consent, content moderation, or settlement. Document:

- obligation and authority;
- identifiers and state translation;
- callback/retry/idempotency behavior;
- failure and reconciliation policy;
- which context owns the anti-corruption translation.

Do not elevate purely technical infrastructure into a domain node.

## Common evidence failures

- Reading only Controller and Service while ignoring XML SQL.
- Treating comments or method names as executed behavior.
- Treating a dead or unreferenced method as a production path.
- Describing a desired expected-old condition that current SQL lacks.
- Claiming no recovery mechanism before checking tasks, Lua, and reconciliation jobs.
- Treating tag, segmentation, or other local modules as missing external contracts without inventorying the repository.
- Declaring asynchronous coverage complete from class existence alone.
- Using code location to decide domain ownership.
