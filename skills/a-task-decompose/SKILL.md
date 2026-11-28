---
name: a-task-decompose
description: "拆分任务/任务分解 | Decompose an approved goal into dependency-aware, vertically sliced, independently verifiable tasks mapped to business logic, decisions, outputs, and completion evidence."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Task Decompose

## Mental model

Decompose by independently valuable engineering outcomes and uncertainty, not directories, commands or required workflow stages. A good slice connects behavior to real integration and verification; it leaves the system coherent at each boundary.

## Plan the slices

- Start from approved goals, non-goals, acceptance criteria, existing contracts and material design decisions. Map every affected rule to an outcome or explicit no-change disposition; infrastructure/research items state their purpose instead of inventing business IDs.
- Prefer vertical slices: implementation, real wiring and relevant tests together. Keep tightly coupled invariants in one slice rather than delivering unsafe intermediate states. Split independent outcomes, distinct risk/authority, separate environments or uncertainties that need their own proof.
- Separate discovery/spikes from production changes: hypothesis, evidence to collect, stop condition, conditional repair only if justified. Separate final host/deployment acceptance when environment or authorization differs; do not let passing local tests imply those gates passed.
- Order by dependencies, not document order. Identify blocking decisions and prerequisites; check for cycles and missing producers/consumers. Protect data/safety and shared contracts before work depending on them. Avoid tasks for individual edits, artificial phases or parallel writers. Use clarification, research, architecture, specification, implementation, verification, alignment and retrospective only where useful; strict review remains the existing gate, not a separate invented Task phase.

## Plan item vs registered Task

For each planned item capture title, goal (observable outcome), scope/non-goals, rule/decision references, dependencies/blockers, `doneWhen`, verification strategy (not fabricated results), and optional suggested mode/risk. Keep dependencies in the plan, not new JSON schema fields. An item is too big if unrelated completion claims cannot be isolated, or unresolved semantics make implementation guesswork; too small if it has no independent outcome.

A plan is not Runtime state. Do not pre-create registered-looking Task JSON for future work. Only when starting work that warrants persistence, create a fresh schema-valid Task with `goal`, `doneWhen`, current Session policy (frozen on start), active/prepare, empty decisions and verification `not_run`, then call `vibe_task_control(action=start)`. Record material decisions through Runtime; actual verification results only after checks. Follow `docs/03-STATE-MACHINE.md` and `schemas/task.schema.json`; never add dependency/strategy fields or change frozen policy. Strict-risk work requires explicit strict mode and a new strict Task. One registered active Task per Session.

## Output and completion

Return an ordered plan of independently verifiable outcomes with dependency/authority boundaries. Under strict policy capture the necessary breakdown before substantial implementation. Complete when every in-scope rule is mapped, dependencies have no unresolved cycle, blockers and conditional work are explicit, each item has credible acceptance, and the next ready item is clear. Preserve remaining plan items as plans; do not manufacture Task completion.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
