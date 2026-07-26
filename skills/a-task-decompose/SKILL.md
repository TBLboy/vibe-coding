---
name: a-task-decompose
description: Decompose an approved goal into dependency-aware, vertically sliced, independently verifiable tasks mapped to lifecycle phases, business logic, decisions, outputs, and completion evidence.
license: MIT
compatibility: codex
metadata:
  stage: task-decomposition
  output: task-list
---

# Task Decompose

## Purpose

Turn an approved goal into a machine-readable execution graph that the Vibe Coding 主代理 can plan autonomously.

## Decomposition Principles

1. Prefer vertical slices that produce an observable result over horizontal piles such as “build all models” then “build all APIs”.
2. Each task must be independently understandable and verifiable.
3. Each implementation task must reference one or more business atoms, unless it is pure infrastructure or research and explicitly marked as such.
4. Separate discovery/spike tasks from production implementation.
5. Separate implementation from verification when verification requires a distinct environment or authority.
6. Do not create a task for every command or file edit.
7. Split a task when it has multiple unrelated completion conditions, multiple owners, or hidden internal phases.
8. Preserve dependencies and critical-path blockers.

## Chain Format

Organize work along the lifecycle:

```text
business-clarification
→ requirement-baseline
→ solution-research
→ architecture-decision
→ task-decomposition
→ engineering-spec
→ implementation
→ verification
→ alignment
→ retrospective
→ distillation
```

Not every increment needs a separate task in every phase, but skipped phases must be intentional and recorded.

## Task Contract

Every non-trivial task includes:

- ID, title, kind, phase, parent/goal;
- objective expressed as an outcome;
- related business logic and decisions;
- inputs and outputs;
- dependencies and blockers;
- plan at a useful level;
- authority and risk;
- `done_when` conditions;
- verification strategy;
- result and follow-ups.

Use `implemented-unverified` when code exists but evidence is incomplete.

## Sizing Test

A task is probably too large when:

- its title contains multiple unrelated verbs;
- it spans unrelated modules;
- its completion cannot be demonstrated with a focused evidence set;
- it requires reopening business clarification mid-implementation;
- failure would make it unclear which assumption was wrong.

A task is probably too small when it is only a single mechanical edit with no independent outcome.

## Output

Update `.project-log/tasks/task-list.yaml`. Keep task order dependency-aware, not merely chronological.

## Completion Gate

- all in-scope atoms are covered by tasks or explicitly need no change;
- dependencies and blockers are explicit;
- no implementation task requires guessing unresolved business semantics;
- every task has verifiable completion conditions;
- the next ready task can be selected mechanically.
