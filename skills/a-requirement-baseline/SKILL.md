---
name: a-requirement-baseline
description: "Freeze a versioned business requirement baseline from clarified atomic logic, scope boundaries, constraints, assumptions, and unresolved questions before technical implementation begins."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Requirement Baseline

## Purpose

Create a temporary but explicit contract for the current increment. A baseline is not a promise that requirements will never change; it defines what is currently approved, what is excluded, and how later changes are handled.

## Location

Each piece of work owns its own baseline:

```text
.vibe/requirements/
├── README.md        # index: | id | title | status | version | tasks |
└── <work>.md        # one baseline per work item; slug = Task ID by default
```

- Create `<work>.md` only when durable business rules need a dedicated home. For a single bounded increment, the Task `goal` + `doneWhen` may be baseline enough; do not create the file by ritual.
- Never put a second work item's rules into an existing baseline; create a new file. Never edit an `active` rule in place; use change control below.
- Rules that turn out to hold across all work are distilled into the project `AGENTS.md` project-level rules and referenced from the baseline, not duplicated.
- Maintain `README.md` on every create / activate / supersede. Create it together with the first baseline; it is the entry point other Skills read to learn which baselines are `active`.
- Reference the baseline path from the Task `goal`; point `doneWhen` at its acceptance criteria.

## Inputs

- clarified business atoms and open questions (`a-business-clarify` output);
- the previous version of this work's baseline, if any (`.vibe/requirements/<work>.md`), and the index `README.md` to spot overlap with other active baselines;
- decisions that constrain the scope (`.vibe/progress.md`, Task `decisions`);
- the active Task and current user confirmations.

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
8. Write the baseline only after all exit conditions are met.

Do not activate a baseline while the clarification gate is open or blocked. Functional rules, current technical facts, and their conflicts must be distinguishable.

## Decision authority

- **A**: reversible, local, low-impact — resolve directly.
- **B**: material but recoverable — resolve, then record it in the active Task JSON `decisions` (or `.vibe/progress.md` when it is a durable project fact).
- **C**: product semantics, safety, data, public interfaces, cost, or irreversible architecture — ask the user; one question, with a recommendation and its consequence.

## Change Control

When a new statement conflicts with an active baseline:

- do not overwrite the old rule in place;
- create a change candidate;
- identify affected atoms, tasks, code, tests, interfaces, migration, and delivery risk;
- use the authority matrix;
- supersede the old baseline only after the change is accepted, and keep the superseded version visible in the file.

## Outputs

`.vibe/requirements/<work>.md` (when warranted) must include:

- ID (the work slug) and version;
- status (`draft` / `active` / `superseded`);
- goal;
- actors;
- in-scope and out-of-scope items;
- business rules with acceptance criteria;
- constraints and quality attributes;
- assumptions;
- unresolved questions;
- evidence/approval;
- dates and supersession metadata;
- a change log of accepted changes to this baseline.

Update `.vibe/requirements/README.md` in the same step.

Point the active Task `doneWhen` at the covered acceptance criteria. When the baseline changes what the user should know about the project stage, summarize it in `.vibe/progress.md`.

## Completion Gate

- all in-scope atoms are active or explicitly experimental;
- every atom has acceptance criteria;
- no blocking conflict remains hidden;
- scope exclusions are explicit;
- change-control behavior is established;
- the baseline is listed in `README.md` with its current status and version.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
