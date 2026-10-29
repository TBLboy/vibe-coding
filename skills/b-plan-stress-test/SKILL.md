---
name: b-plan-stress-test
description: "Stress-test a proposed plan or design through one focused question at a time, resolving decision dependencies with evidence and a recommended answer."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Plan Stress Test

## Purpose

Use when the user asks to be grilled, wants a plan pressure-tested, or needs to uncover missing design decisions before committing.

## Method

1. Read available project facts (`AGENTS.md`, `.vibe/progress.md`, active Task) and inspect the codebase before asking anything discoverable.
2. Map the plan's goals, actors, interfaces, states, dependencies, failure paths, constraints, security, cost, operational ownership, and rollback.
3. Ask one highest-impact unresolved question at a time.
4. Give a recommended answer, its impact, and the evidence or assumption behind it.
5. Follow dependent branches until the plan has a coherent decision path.

## Decision authority

- **A**: reversible, local, low-impact — resolve directly.
- **B**: material but recoverable — resolve, then record it in the active Task JSON `decisions` (or `.vibe/progress.md` when it is a durable project fact).
- **C**: product semantics, safety, data, public interfaces, cost, or irreversible architecture — ask the user; one question, with a recommendation and its consequence.

Do not turn ordinary implementation choices into an endless interview. Record material B-level decisions and stop for C-level product, safety, data, public-interface, cost, or irreversible architecture decisions.

## Output

Maintain a compact decision list: question, options, recommendation, chosen answer, owner, and remaining risk. When the plan belongs to an active project, persist each material decision in the Task JSON `decisions` (durable ones also in `.vibe/progress.md`) and, while the plan is still open, note the next unresolved question in the Session's `current-session.md`.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
