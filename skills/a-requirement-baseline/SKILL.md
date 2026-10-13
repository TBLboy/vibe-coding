---
name: a-requirement-baseline
description: Freeze a versioned business requirement baseline from clarified atomic logic, scope boundaries, constraints, assumptions, and unresolved questions before technical implementation begins.
license: MIT
compatibility: codex
metadata:
  stage: requirement-baseline
  output: baseline
---

# Requirement Baseline

## Purpose

Create a temporary but explicit contract for the current increment. A baseline is not a promise that requirements will never change; it defines what is currently approved, what is excluded, and how later changes are handled.

## Inputs

- `vibe record list --kind business-atom` (clarified atoms)
- `vibe record list --kind open-question` (deferred or answered questions)
- `vibe record list --kind requirement` (the previous baseline, if any)
- `vibe record list --kind decision` (decisions that constrain the scope)
- `vibe context <task-id>` for the active increment, plus current user confirmations

## Baseline Rules

1. Include only business atoms relevant to the current goal.
2. An atom may be activated when it is user-confirmed, evidence-derived without material conflict, or explicitly experimental.
3. Inferred behavior that changes product semantics cannot become active without appropriate confirmation.
4. Every active atom needs at least one acceptance criterion.
5. Record in-scope and out-of-scope items separately.
6. Record assumptions with an owner and invalidation trigger.
7. Unresolved questions must state whether they block implementation.
8. Baseline changes after implementation starts require impact analysis.

## Workflow

1. Identify the baseline goal and increment boundary.
2. Select covered business atoms.
3. Verify atom status, authority, acceptance criteria, and conflicts.
4. Consolidate shared actors, constraints, quality attributes, and external dependencies.
5. List exclusions and deferred behavior.
6. List blocking and non-blocking unresolved questions.
7. Create or increment a baseline version.
8. Record the baseline through `vibe record create|update` only after all exit conditions are met.

Do not activate a baseline while the clarification gate is open or blocked. Functional rules, current technical facts, and their conflicts must be distinguishable.

## Change Control

When a new statement conflicts with an active baseline:

- do not overwrite the old rule in place;
- create a change candidate;
- identify affected atoms, tasks, code, tests, interfaces, migration, and delivery risk;
- use the authority matrix;
- supersede the old baseline only after the change is accepted.

## Outputs

Persist the baseline with `vibe record create|update --kind requirement` and link it to the atoms it covers (`vibe record link`). When the increment changes what the user should know, summarize it in `.project-log/progress.md` and the active work in `.project-log/current-session.md` via `vibe memory sync --file <json>`. Do not write format 1 YAML files.

The baseline must include:

- ID and version;
- status;
- goal;
- actors;
- in-scope and out-of-scope items;
- business logic references;
- constraints and quality attributes;
- assumptions;
- unresolved questions;
- evidence/approval;
- timestamps and supersession metadata.

## Completion Gate

- all in-scope atoms are active or explicitly experimental;
- every atom has acceptance criteria;
- no blocking conflict remains hidden;
- scope exclusions are explicit;
- change-control behavior is established.
