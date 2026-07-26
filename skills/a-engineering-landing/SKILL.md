---
name: a-engineering-landing
description: Implement an approved engineering task with controlled scope, traceability to business logic, incremental validation, project-log updates, and explicit handling of deviations or newly discovered ambiguity.
license: MIT
compatibility: codex
metadata:
  stage: implementation
  output: implemented-change
---

# Engineering Landing

## Purpose

Land production-quality code, configuration, tests, or documentation according to the approved task and specification.

## Before Editing

Confirm:

- the task is `ready` or `in-progress`;
- blocking dependencies are done;
- relevant business atoms and acceptance conditions are known;
- an engineering spec exists for non-trivial work;
- required C-level decisions are resolved.

Prototype/spike work may proceed with explicit `experimental` status and must not be presented as production completion.

## Implementation Rules

1. Make the smallest coherent change that satisfies the task.
2. Preserve unrelated behavior.
3. Follow existing project conventions unless a recorded decision changes them.
4. Keep external dependencies behind a controlled boundary where practical.
5. Add or update tests alongside behavior.
6. Add observability for important failures and state transitions.
7. Avoid silent fallback that hides broken requirements.
8. Do not broaden scope merely because adjacent cleanup is attractive; create follow-up tasks.
9. When code reveals a business ambiguity, stop that branch, classify it, and return to `a-business-clarify` if needed.
10. When the implementation must diverge from the spec, update the decision/spec before declaring completion.

## Incremental Validation

Run the narrowest useful checks after each meaningful slice, then broader checks before handoff:

- formatting/static analysis;
- focused unit/component tests;
- integration tests;
- regression tests;
- build/package checks;
- environment/hardware validation where applicable.

Record commands and evidence in the task.

## Status Rules

- `in-progress`: implementation is being modified;
- `blocked`: cannot proceed without a dependency or decision;
- `implemented-unverified`: planned outputs exist, but required evidence is incomplete;
- `done`: all completion conditions and verification requirements passed.

## Outputs

Update task results, changed files, decisions, implementation references in business atoms, current session, and any new follow-up tasks.
