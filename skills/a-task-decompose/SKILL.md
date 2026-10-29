---
name: a-task-decompose
description: "Decompose an approved goal into dependency-aware, vertically sliced, independently verifiable tasks mapped to business logic, decisions, outputs, and completion evidence."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Task Decompose

## Purpose

Turn an approved goal into an ordered, dependency-aware set of work items that the main Agent can execute and verify one at a time.

## Decomposition Principles

1. Prefer vertical slices that produce an observable result over horizontal piles such as "build all models" then "build all APIs".
2. Each task must be independently understandable and verifiable.
3. Each implementation task must reference one or more business rules, unless it is pure infrastructure or research and explicitly marked as such.
4. Separate discovery/spike tasks from production implementation.
5. Separate implementation from verification when verification requires a distinct environment or authority.
6. Do not create a task for every command or file edit.
7. Split a task when it has multiple unrelated completion conditions, multiple owners, or hidden internal phases.
8. Preserve dependencies and critical-path blockers.

## Lifecycle Coverage

Check each increment against the lifecycle and decide intentionally which stages need their own work item:

```text
business clarification → requirement baseline → research → architecture decision
→ task decomposition → engineering spec → implementation → verification
→ (strict only) independent review → alignment → retrospective
```

Not every increment needs a separate item in every stage, but skipped stages must be intentional and stated.

## Task Contract

Every non-trivial work item maps onto the V2 Task JSON:

- `id`, `title` — one outcome, one verb;
- `goal` — objective expressed as an outcome;
- `doneWhen` — observable completion conditions, each verifiable;
- `policy` — frozen from the Session mode when the Task starts;
- `decisions` — related business rules and decisions it depends on;
- `verification` — strategy now, results later;
- `blocker` / `nextAction` — dependencies and the next mechanical step.

Order the items dependency-first, not merely chronologically. Only items that need durable tracking or recovery become files under `.vibe/tasks/`; the rest stay in the plan.

## Sizing Test

A task is probably too large when:

- its title contains multiple unrelated verbs;
- it spans unrelated modules;
- its completion cannot be demonstrated with a focused evidence set;
- it requires reopening business clarification mid-implementation;
- failure would make it unclear which assumption was wrong.

A task is probably too small when it is only a single mechanical edit with no independent outcome.

## Output

The ordered task list with dependencies, plus the Task JSON files that warrant persistence. Under strict policy, the breakdown is captured before substantial implementation.

## Completion Gate

- all in-scope rules are covered by tasks or explicitly need no change;
- dependencies and blockers are explicit;
- no implementation task requires guessing unresolved business semantics;
- every task has verifiable completion conditions;
- the next ready task can be selected mechanically.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
