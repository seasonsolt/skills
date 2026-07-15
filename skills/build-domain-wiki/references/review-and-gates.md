# Adversarial review and quality gates

## Independent review objective

Use this review stance:

> Find evidence that can overturn the current domain division, rule statement, completeness claim, or evidence status. Do not optimize for confirming the author’s model.

When delegating review, give the reviewer the wiki, repository roots, baselines, and this objective. Do not leak the author’s intended answer or ask for stylistic praise.

Prefer a reviewer or agent that did not author the wiki. Record reviewer identity, review date, wiki revision, and code baselines. If independence is unavailable, disclose self-review as a limitation rather than presenting it as independent validation.

## Review prompt template

```text
Independently review the domain wiki at <wiki-root> against the source repositories listed in its repository baseline.

Your primary objective is to find evidence that could disprove the current bounded-context division or stated business rules. Treat service names, package locations, RPC direction, tables, and existing wiki conclusions as hypotheses rather than truth.

Check at least:
1. omitted frontends, backends, long-tail capabilities, and external business contracts;
2. two contexts sharing a table, state machine, identifier, or bidirectional writes;
3. false implementation claims, including MyBatis mapper XML, Wrapper, annotations, Lua, database constraints, jobs, MQ consumers, and callbacks;
4. target rules incorrectly described as current behavior;
5. asynchronous paths whose deployment, subscription, scheduling, idempotency, tenant context, or retry behavior is unverified;
6. duplicated or undefined CAP/Q/RULE/SCN/EVT identifiers;
7. glossary files polluted by implementation details;
8. quality reports that overstate structural, evidence, runtime, or business completion.

Report findings by severity with exact wiki and source references. For each finding, state the counterevidence, what conclusion it invalidates, and the smallest honest remediation. Also list unresolved hypotheses requiring runtime configuration or business confirmation.
```

## Mechanical gates

Require:

- all internal Markdown links resolve;
- all context and subdomain homepages contain required metadata;
- stable identifier definitions are unique and all references resolve;
- `CAP-*` definitions belong to the coverage ledger;
- stable `SCN-*` and `EVT-*` do not appear in subdomain pages;
- `CONTEXT.md` contains no implementation paths, frameworks, APIs, SQL, or deployment details;
- every discovered capability is classified or explicitly excluded;
- no knowledge is marked confirmed without confirmation authority and date.

Run:

```bash
ruby <skill-dir>/scripts/validate_domain_wiki.rb <wiki-root>
```

Treat the script as a floor, not proof of semantic correctness.

## Modeling gates

Verify manually:

- capability names describe business abilities rather than CRUD/controllers;
- subdomains and contexts are not assumed 1:1;
- context relationships are not inferred directly from RPC technology;
- aggregate candidates name the invariant and concurrency boundary they protect;
- state machines separate current behavior from targets;
- shared tables and cross-writes are recorded as boundary counterevidence;
- code location is not used as the sole ownership argument;
- long-tail capabilities and external business contracts are represented.

## Evidence gates

For every deep context, verify:

- synchronous command path is traced;
- Mapper XML/annotation/Wrapper and database constraints are checked;
- caches, Lua, secondary stores, and external side effects are checked;
- messages, jobs, callbacks, retries, and reconciliation paths are registered;
- expected-old state, idempotency, tenant, and concurrency conditions are stated;
- evidence file paths and commits are recorded;
- file discovery is not mislabeled as runtime verification.

If any important path remains open, overall coverage is `部分观察` even when individual static facts are verified.

## Remediation record

For every material review finding, record:

| Finding | Evidence | Invalidated claim | Action | Residual question |
| --- | --- | --- | --- | --- |

Allowed outcomes:

- corrected;
- reclassified as a competing hypothesis;
- moved to an explicit evidence gap;
- deferred for runtime verification;
- deferred for business confirmation;
- rejected with evidence-based rationale.

Do not mark a finding resolved merely because it was mentioned in an open-question list.

## Honest final report

Report four independent outcomes:

1. **Structural gate** — documents, metadata, links, and identifiers.
2. **Modeling gate** — separation of spaces, language, boundaries, and hypotheses.
3. **Evidence gate** — static path completeness and known gaps.
4. **Confirmation gate** — runtime and authorized business confirmation.

Prefer conclusions such as “structure passed; evidence conditionally passed; runtime and business confirmation pending” over a single ambiguous “complete.”

Include exact counts generated from definitions, not naive occurrence counts. For example, count `CAP-*` definitions only from coverage-ledger definition rows, then separately verify all references resolve.
