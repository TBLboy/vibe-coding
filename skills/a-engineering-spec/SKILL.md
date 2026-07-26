---
name: a-engineering-spec
description: Produce a task-specific engineering specification that maps business logic and architecture to concrete modules, interfaces, data changes, failure behavior, tests, migration, rollout, and rollback.
license: MIT
compatibility: codex
metadata:
  stage: engineering-spec
  output: task-specification
---

# Engineering Spec

## Purpose

Remove implementation ambiguity without rewriting the entire project design. A specification is created per meaningful task or coherent task group.

## Required Sections

Create `.project-log/specs/<TASK-ID>.md` from the template and include:

1. Task objective and non-goals.
2. Related business atoms and acceptance criteria.
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
- Reuse existing patterns when they remain valid; record deviations.
- Call `a-solution-research` when a non-trivial technical choice is unresolved.
- Reopen business clarification when implementation exposes a genuine product ambiguity.
- Make assumptions explicit and temporary.

## Completion Gate

The task can be implemented by another competent Agent without needing to rediscover the business intent, while retaining freedom over low-level reversible details.
