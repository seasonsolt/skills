---
name: build-domain-wiki
description: Build, review, and maintain a full-coverage, evidence-backed DDD domain wiki with graded depth, bounded-context discovery, ubiquitous language, scenarios, rules, events, implementation evidence, adversarial review, and quality gates. Use only when the user explicitly invokes `$build-domain-wiki` or explicitly asks to use the `build-domain-wiki` skill by name. Never infer, auto-trigger, or silently invoke this skill from generic requests about DDD, architecture, documentation, code understanding, or testing.
---

# Build Domain Wiki

## Enforce explicit invocation

Run this workflow only after the user explicitly names `$build-domain-wiki` or `build-domain-wiki`. If the skill was loaded without that explicit request, do not execute it or alter domain documentation.

Never silently apply this skill, even when the request appears to match perfectly.

## Produce the right knowledge product

Build a human-governed domain knowledge base, not an automatically generated code wiki. Use code, UI, SQL, configuration, messages, jobs, and external APIs as evidence about current behavior; never let implementation structure automatically define business boundaries or business truth.

Use the governing strategy:

- Cover the entire business breadth before claiming completion.
- Deepen strategically important contexts after breadth is classified.
- Separate subdomains, bounded contexts, microservices, repositories, and deployment units.
- Separate confirmed business facts, current implementation observations, target-model candidates, and open questions.
- Preserve uncertainty and counterevidence instead of forcing premature conclusions.

## Read the bundled guidance

Read these references before the corresponding phase:

1. Always read [output-contract.md](references/output-contract.md) and [discovery-workflow.md](references/discovery-workflow.md) before creating or restructuring the wiki.
2. Read [implementation-evidence.md](references/implementation-evidence.md) before inspecting code or deepening contexts. Apply its MyBatis-Plus section when that framework is present.
3. Read [review-and-gates.md](references/review-and-gates.md) before independent review, remediation, or final acceptance.

## Execute the workflow

### 1. Establish scope and authority

- Read repository instructions first.
- Confirm the wiki root, business scope, source repositories, and whether existing architecture or AI-workspace documentation is an input, peer, or explicitly excluded.
- Confirm whether runtime environments, logs, configuration, credentials, or production-derived data may be inspected. Without explicit authority, stay with static evidence and mark runtime behavior unverified.
- Do not silently merge an independent domain wiki into another documentation constitution.
- Record the POC or production status and the intended audience.
- Treat “full coverage” as complete classification of discovered breadth, not equal depth everywhere.

### 2. Establish a reproducible code baseline

- Inventory the root repository and all nested repositories or source snapshots.
- Record current commits, branches, dirty-worktree state, missing repositories, and unavailable configuration.
- Before formal analysis, update local default branches only when the user authorized repository updates. Never reset, discard, overwrite, or pull across dirty user changes. If authorization is absent or safe updating is impossible, preserve the state and record the limitation.
- When `.codegraph/` exists, use CodeGraph before grep/find or broad file reading for code discovery and call-path understanding.

### 3. Complete breadth-first discovery

- Inventory every frontend, backend, shared contract, database migration, scheduled job, message consumer, callback, and external business integration in scope.
- Maintain a discovery-surface denominator by repository and surface type, recording checked, excluded, missing, and not-authorized sources. Do not define completeness only as “everything already discovered was classified.”
- Discover actors, goals, entry points, user journeys, business objects, commands, decisions, results, and external obligations.
- Build a coverage ledger before deep modeling.
- Classify long-tail capabilities explicitly; do not equate “main transaction path covered” with “whole domain covered.”
- Record missing implementations and ambiguous capabilities as evidence gaps or open questions, never as silently omitted scope.

### 4. Model the problem space and model space separately

- Build the subdomain map from business problems, differentiation, and value.
- Build the bounded-context map from language, invariants, lifecycle, ownership, and translation needs.
- Add an explicit subdomain-to-context mapping supporting 1:1, 1:N, N:1, and competing hypotheses.
- Do not infer a context relationship solely from Feign, Dubbo, MQ, database, package, or repository relationships.
- Seek evidence that could collapse or split candidate contexts. Shared tables, bidirectional writes, shared state machines, and bypass updates are strong counterevidence.

### 5. Apply graded depth

- Give every discovered subdomain and context the baseline metadata and minimum semantic coverage defined in the output contract.
- Deepen strategically important, high-risk, or boundary-ambiguous contexts with scenarios, rules, invariants, state transitions, aggregate candidates, events, policies, and implementation evidence.
- Express important scenarios as: actor → command → decision rules → domain event → downstream policy → business result.
- Keep each `CONTEXT.md` a glossary only. Put scenarios, code evidence, architecture, APIs, and data details elsewhere.

### 6. Verify implementation evidence end to end

- Trace synchronous and time/event-driven paths.
- Inspect business entry, orchestration, persistence, custom SQL, atomic conditions, database constraints, caches/scripts, messages, scheduled jobs, callbacks, and external side effects.
- For MyBatis-Plus systems, always inspect `mapper/*.xml`, annotations, Query/Update/Lambda Wrappers, interceptors, tenant behavior, logic deletion, optimistic locking, and database constraints.
- Record exact source paths and code baselines. Mark file existence separately from deployment, subscription, scheduling, and runtime verification.
- Preserve contradictions between scenario candidates and current behavior. Never rewrite a target rule as if current code already enforced it.

### 7. Govern knowledge and evidence independently

- Only authorized domain owners can mark business knowledge confirmed.
- Static code agreement, passing tests, or developer agreement does not equal business confirmation.
- Use independent evidence status and evidence-coverage fields.
- Downgrade claims when the full path is incomplete. “Statically verified + partial observation” is valid and preferable to a false closure claim.

### 8. Run adversarial review and remediation

- Review with the explicit objective of finding evidence that can overturn the current domain division or stated rules.
- Prefer a different agent or reviewer from the author. Record reviewer identity, review date, and code/wiki baselines; disclose the limitation when only self-review is possible.
- Check omissions, duplicated identifiers, false implementation facts, service-shaped boundaries, missing long-tail capabilities, unexamined external contracts, and asynchronous bypasses.
- Track every material finding as corrected, reclassified, explicitly deferred, or rejected with rationale.
- Do not accept code location as sufficient evidence for domain ownership.

### 9. Validate and report honestly

- Run `ruby scripts/validate_domain_wiki.rb <wiki-root>` from this skill directory, adapting only if the project intentionally uses a different document contract.
- Perform the semantic gates in [review-and-gates.md](references/review-and-gates.md); the script cannot confirm business correctness.
- Report exact counts, baselines, limitations, and unresolved questions.
- Distinguish structural acceptance, evidence acceptance, runtime verification, and business confirmation.
- Never declare the POC fully complete merely because Markdown structure passes.

### 10. Maintain without corrupting domain truth

- Use repository diffs to identify stale evidence pages and impacted scenarios, rules, or contexts.
- Automation may propose evidence updates, but must not silently rewrite confirmed terminology, business rules, context boundaries, or confirmation status.
- Re-run adversarial review after boundary-affecting changes.
- Keep technical/code wikis as peers and link them through explicit context-to-service mappings rather than copying them into the domain glossary.

## Preserve identifier ownership

- Define `CAP-*` once in the coverage ledger; reference it elsewhere.
- Define stable `SCN-*` and `EVT-*` only in bounded-context scenario documents; subdomains describe scenario/event semantics without owning those identifiers.
- Define each `RULE-*` and `Q-*` once, with all other uses treated as references.
- Never reuse one stable identifier for different semantics.

## Stop conditions

Do not claim completion until:

- all discovered capabilities are classified;
- every subdomain and bounded context has required metadata;
- context and subdomain maps are separate and explicitly mapped;
- critical contexts have synchronous and time/event-driven evidence;
- missing repositories, runtime uncertainty, and business uncertainty are visible;
- internal links and stable identifiers validate;
- an adversarial review has been remediated;
- the final report states what remains unconfirmed.

Do not commit, push, update external systems, or mark business knowledge confirmed unless the user separately authorizes that action.
