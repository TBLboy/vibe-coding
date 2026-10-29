---
name: a-engineering-spec
description: "Produce a task-specific engineering specification that maps business logic and architecture to concrete modules, interfaces, data changes, failure behavior, tests, migration, rollout, and rollback."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Engineering Spec

## Purpose

Remove implementation ambiguity without rewriting the entire project design. A specification is created per meaningful task or coherent task group.

## Required Sections

Write the spec for the Task (as the reply, or as a project document the user chooses — V2 does not mandate a spec directory) and include:

1. Task objective and non-goals.
2. Related business rules and acceptance criteria (the Task `doneWhen`).
3. Existing behavior and evidence.
4. Target behavior.
5. Files/modules/components likely affected.
6. Interface and schema changes.
7. State, concurrency, transaction, and lifecycle behavior.
8. Validation, error handling, retry, timeout, and idempotency.
9. Security/privacy implications.
10. Logging, metrics, and diagnostics.
11. Compatibility, migration, feature flag, rollout, and rollback.
12. Test matrix and acceptance evidence.
13. Open questions and authority level.

## Rules

- Describe outcomes and contracts, not line-by-line code.
- Do not invent new product behavior to make implementation convenient.
- Reuse existing patterns when they remain valid; record deviations as Task `decisions`.
- Use `a-deep-research` when a non-trivial technical choice is unresolved.
- Reopen business clarification (`a-business-clarify`) when implementation exposes a genuine product ambiguity.
- Make assumptions explicit and temporary.
- Under strict policy, the spec's acceptance criteria and technical decisions must be captured before substantial implementation.

## Completion Gate

The task can be implemented by another competent Agent without needing to rediscover the business intent, while retaining freedom over low-level reversible details.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
