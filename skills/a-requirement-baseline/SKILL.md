---
name: a-requirement-baseline
description: "需求基线/冻结需求 | Freeze a versioned business requirement baseline from clarified atomic logic, scope boundaries, constraints, assumptions, and unresolved questions before technical implementation begins."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Requirement Baseline

## Mental model

A baseline is a versioned contract for an approved increment, not a permanent freeze, technical design or claim of implementation. Preserve the distinction between confirmed behavior, experimental behavior, current implementation facts and verification status.

## Construct the contract

Use clarified atoms and latest confirmations, relevant existing active baselines (via index), project rules, durable decisions and current Task criteria. Reconcile overlaps and conflicts before activation. Apply these quality dimensions:

- **Atomicity:** split independently implementable, changeable, failing or acceptable behavior; not by sentence or module.
- **Completeness:** cover accepted functional rules, constraints, high-impact exceptions and explicit non-goals; retain unaffected contracts.
- **Accuracy:** remove rejected proposals and obsolete assumptions; distinguish observed code from intended behavior.
- **Derivation:** add only necessary implications of confirmed rules and existing constraints, with premise; optional or material C behavior requires approval.
- **Traceability:** each durable atom has a stable unique ID, rule, observable acceptance (Given/When/Then when useful), source and authority. Separate user confirmation, existing contracts, evidence-derived implications and assumptions.
- **Proportionality:** group complex rules by domain; for a bounded increment `goal`/`doneWhen` may suffice. Do not freeze future technical solutions as business requirements.

Activate only user-confirmed or evidence-derived rules without material conflict, or explicitly labeled experimental rules. Never activate inferred product-semantic changes without confirmation. Each atom needs acceptance criteria; assumptions need owner/invalidation trigger; unresolved questions identify whether they block implementation. No activation while a blocking clarification conflict remains.

## Persistence and change control

When a durable baseline is warranted, use `.vibe/requirements/<work>.md` (work slug, normally Task ID), one file per work item. Maintain `.vibe/requirements/README.md` on create/activate/supersede with id, title, status, version and related Task IDs. Use `draft` / `active` / `superseded` and retain history. Stable cross-work project rules belong in AGENTS.md only with user approval; reference rather than duplicate them.

For complex work organize metadata (ID/version/status/dates), goal/actors/scope, domain-grouped rules and acceptance, constraints/quality attributes, non-goals, assumptions/open questions, related existing contracts, source/approval, change log and supersession metadata. This is a reference structure, not a required template for trivial work.

When new information conflicts with an active baseline, create a change candidate; trace affected atoms, Tasks, code, tests, interfaces, migration and delivery risks. A local reversible decision may be resolved directly; B material recoverable decisions via Runtime `record_decision` or durable `.vibe/progress.md`; C product semantics, public interfaces, safety, data, cost or irreversible choices require user approval. Supersede only after acceptance and preserve the superseded version; never overwrite an `active` rule in place or mix another work item's rules into it.

Reference the baseline in Task `goal` and acceptance in `doneWhen` **before registration**. Registered criteria cannot be edited: compatible clarifications use `record_decision` in prepare/implement; if scope or acceptance changes materially, follow the supersession rule in `docs/06-AGENT-CONTRACT.md` and start a new Task with the approved criteria. Do not change frozen Policy. See `docs/03-STATE-MACHINE.md`. Update progress only for durable project-level changes. When a change is approved, reconcile affected current summaries and technical references; keep the prior baseline and supersession links. A code discrepancy is a finding, not authority to revise the rule.

## Completion

Check against actual user confirmations/corrections and existing authority: unique IDs, independent observable acceptance, scope coverage, retained rules, explicit exclusions, authority/source, open-question status, version/index consistency and accepted change history. Distinguish an active baseline from implemented or verified behavior. Report unresolved blockers rather than activating by ceremony.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
