---
name: a-architecture-decision
description: "Convert an approved requirement baseline and technical recommendation into explicit module boundaries, interfaces, data flows, failure handling, operational constraints, and recorded architecture decisions."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Architecture Decision

## Purpose

Define only the architecture necessary for the current increment. Avoid both accidental architecture and speculative over-design.

## Inputs

- the approved requirement baseline for this work (`.vibe/requirements/<work>.md` when it exists, otherwise the confirmed rules in the active Task `goal`/`doneWhen`);
- the clarified atomic business rules;
- technical research results (`a-deep-research`);
- the current codebase and its constraints;
- decisions already recorded in `.vibe/progress.md` and the active Task JSON.

## Required Views

Describe, at the minimum useful depth:

1. **Responsibilities** — modules/services/nodes and what each owns.
2. **Interfaces** — APIs, events, topics, actions, files, schemas, or device boundaries.
3. **Data flow** — source, transformations, ownership, persistence, and destinations.
4. **State and concurrency** — state owner, synchronization, lifecycle, retries, idempotency.
5. **Failure behavior** — detection, containment, recovery, user-visible result, logging.
6. **Security and privacy** — trust boundaries, permissions, secrets, sensitive data.
7. **Observability** — logs, metrics, traces, health indicators, diagnostics.
8. **Deployment and compatibility** — environments, versions, hardware, migration, rollback.

## Decision authority

- **A**: reversible, local, low-impact — resolve directly.
- **B**: material but recoverable — resolve, then record it in the active Task JSON `decisions` (or `.vibe/progress.md` when it is a durable project fact).
- **C**: product semantics, safety, data, public interfaces, cost, or irreversible architecture — ask the user; one question, with a recommendation and its consequence.

## Decision Discipline

- Record material choices as decisions, each with the rule it supports and the alternative rejected.
- Prefer reversible boundaries and narrow adapters around external dependencies.
- Do not let a framework dictate product behavior.
- Use C authority for irreversible, externally visible, security-sensitive, costly, or migration-heavy decisions.
- Mark hypotheses that require a spike; do not disguise them as settled architecture.

## Output

Return the architecture as a concise written baseline using the views above. Persist only what is durable: material decisions into the active Task JSON `decisions`; architecture constraints that bind future work into `.vibe/progress.md` ("Durable decisions") or into the project `AGENTS.md` when they are stable rules. Each recorded decision should reference the business rule it serves.

## Completion Gate

- ownership and interfaces are unambiguous;
- critical data and failure paths are described;
- external dependencies are isolated behind defined boundaries where practical;
- high-impact decisions are approved;
- the architecture is sufficient for task decomposition without inventing new product behavior.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
