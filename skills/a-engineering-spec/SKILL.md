---
name: a-engineering-spec
description: "工程规格/技术设计/实现方案 | Produce a task-specific engineering specification that maps business logic and architecture to concrete modules, interfaces, data changes, failure behavior, tests, migration, rollout, and rollback."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Engineering Spec

## Mental model

Translate approved behavior and architecture into implementable contracts without inventing product rules or prescribing reversible code details. A spec closes consequential implementation ambiguity: another competent engineer should know where behavior lives, how it works and how to prove it, while retaining implementation freedom.

## Design from real paths

Start with objective, non-goals, approved rules/acceptance, current production paths, relevant architecture decisions and constraints. For each changed behavior trace trigger → entrypoint → owner → state/effects → response/failure → acceptance. Identify affected callers, files/modules and existing extension points; record unchanged contracts and necessary integration/config wiring. State the target delta rather than restating all project design.

Choose relevant design dimensions, not thirteen mandatory sections:

| Dimension | Specify when material |
|---|---|
| Responsibilities and interfaces | owner/caller, signatures or data shape, validation, semantic pre/postconditions, existing consumers |
| State and data | source of truth, schema/defaults, transitions, invariants, transaction/atomicity, concurrency/ordering |
| Failure behavior | errors, retries/timeouts, idempotency, partial failure, cancellation and cleanup |
| Security/privacy | authorization, trust boundaries, input handling, secrets, sensitive effects |
| Operations | necessary logs/diagnostics, environment constraints, compatibility, migration, flags/rollout, rollback/data implications |
| Verification | rule → affected path → observable oracle, positive/negative and retained behavior, environment and limitations |

Specify only meaningful decisions and constraints; do not invent flags, metrics, layers or migration when not required. A local UI change might need behavior, component/state boundary and acceptance only; an API change needs semantic error/permission contracts and consumers; a data migration needs integrity, compatible sequence, recovery and representative evidence. Do not require pseudocode or line-by-line instructions unless ambiguity warrants it.

## Decisions, output and completion

Use existing patterns where sound; record material recoverable deviations through Runtime `record_decision` or durable progress. Use `a-deep-research` for feasibility uncertainty, `a-architecture-decision` for unresolved structural tradeoffs and `a-business-clarify` for genuine semantic ambiguity. Mark assumptions, validation plan and blocking questions; C decisions require user approval before affected implementation. No silent scope changes or frozen criteria edits.

Return inline spec for small work or `.vibe/docs/specs/<task-id>.md` (or meaningful work slug before a Task exists) when durable. Under strict policy capture scope, acceptance and material technical decisions before substantial implementation. A complete spec connects approved rules to real ownership/wiring and observable acceptance, describes relevant failures and compatibility, and leaves no material product or technical ambiguity hidden. Do not claim the design is implemented or verified.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
