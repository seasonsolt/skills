# Breadth-first discovery and modeling

## 1. Freeze the discovery contract

Record:

- included business and product scope;
- excluded sources and documentation constitutions;
- repository roots and nested repositories;
- current commit and dirty state of every source;
- whether the deliverable is a POC or governed knowledge source;
- required breadth and depth policy;
- users who can confirm business meaning.
- runtime/log/configuration access authority and privacy constraints.

For a POC, the modeling method may be experimental while the covered business breadth is still complete. Do not mistake “POC” for “model one convenient subdomain.”

## 2. Update code baselines safely

If explicitly authorized:

1. Identify the default branch of every repository.
2. Inspect dirty worktrees and untracked files.
3. Fetch and fast-forward only safe, clean default branches.
4. Preserve user changes and never reset or force checkout.
5. Record repositories that cannot be updated and continue with their exact local commit as a qualified baseline.

## 3. Inventory every discovery surface

Inspect and classify:

- web, mobile, mini-program, admin, and embedded frontends;
- backend applications and shared libraries/contracts;
- controllers/routes and user-visible entry points;
- jobs, consumers, listeners, callbacks, and workflow processors;
- relational schema/migrations, custom SQL, caches, search indexes, and scripts;
- third-party APIs with business obligations;
- menus, feature flags, and configuration that expose or hide capabilities;
- Git history when it explains why a surprising design exists.

Use CodeGraph first in indexed repositories. Use broad text searches only for surfaces CodeGraph cannot enumerate well, such as XML, SQL migrations, configuration, Lua, static menus, and documentation.

Maintain an explicit denominator matrix rather than relying on discovered-item counts:

| Source/repository | UI/routes | APIs | jobs | MQ/listeners | SQL/migrations | external contracts | runtime | Status/rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

Use `checked`, `excluded`, `missing`, `not authorized`, and `not applicable` consistently. A breadth claim is valid only when every declared source/surface cell has a disposition.

## 4. Build the coverage ledger

Start from business observations, not service names. Give each capability one stable `CAP-*` definition and classify:

- actor and desired outcome;
- originating UI/API/job/external trigger;
- candidate subdomain;
- candidate bounded context;
- source repositories;
- depth tier;
- evidence status;
- open questions.

Keep an explicit unclassified queue during discovery. Completion requires reducing it to zero by classification, exclusion with rationale, or evidence-gap registration.

## 5. Find long-tail capabilities

After the main transaction paths, search for lower-volume capabilities that are easy to miss:

- invoices, notifications, mailing, forms, membership products;
- AI or human-assistance features;
- stations/sites, secondary wallets, withdrawals, reconciliation;
- admin-only capabilities and batch operations;
- external channel-specific obligations;
- obsolete-looking code that may still be deployed.

Classify each item even when it remains shallow.

## 6. Build the subdomain map

Group business problems by value and differentiation. Classify core/supporting/generic only as a candidate unless strategy owners confirm it.

Test each proposed subdomain:

- Does it solve one coherent business problem?
- Does its language remain meaningful without implementation names?
- Would the business invest in changing it independently?
- Is it actually a capability inside a larger problem rather than a subdomain?

## 7. Build the bounded-context map independently

Find boundaries using:

- different meanings for the same word;
- different lifecycles or invariants;
- different sources of truth;
- different change cadence or organizational ownership;
- explicit model translation;
- consistency requirements.

Then seek counterevidence:

- two candidates share one table and state column;
- both write the same aggregate state;
- bidirectional RPC exposes the same model;
- jobs or wrappers bypass the declared owner;
- one identifier/state machine spans both candidates.

When evidence conflicts, preserve competing hypotheses rather than choosing by code location.

## 8. Map problem space to model space

Record 1:1, 1:N, N:1, and unresolved mappings. This prevents stable identifiers, rules, or ownership from being duplicated at subdomain and context layers.

## 9. Select graded depth

Deepen contexts with the strongest combination of:

- strategic differentiation;
- financial or regulatory impact;
- state-machine complexity;
- concurrency or distributed consistency risk;
- high cross-context coupling;
- boundary ambiguity;
- frequent change or incident history.

All other contexts still receive the baseline output contract.

## 10. Model scenarios and language

For each deep context:

1. Define local language without implementation terms.
2. Express scenarios as actor → command → rule → event → policy → result.
3. Identify invariants and concurrency conditions.
4. Draft state transitions with current, target, and unknown semantics separated.
5. Record aggregate candidates and what invariant each would protect.
6. Add open questions with the role best able to answer them.
