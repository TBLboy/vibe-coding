---
name: a-engineering-landing
description: "Implement an approved engineering task with controlled scope, traceability to business logic, incremental validation, V2 Task updates, and explicit handling of deviations or newly discovered ambiguity."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Engineering Landing

## Purpose

Land production-quality code, configuration, tests, or documentation according to the approved task and specification.

## Before Editing

Confirm:

- the Task (if persistent) is `active` with `phase` `implement`, and its `policy` is known (it was frozen at Task start);
- blocking dependencies are done;
- relevant business rules and acceptance conditions (`doneWhen`) are known;
- an engineering spec exists for non-trivial work (`a-engineering-spec`);
- required C-level decisions are resolved.

Prototype/spike work may proceed when explicitly labeled experimental and must not be presented as production completion.

## Risk routing

Classify before editing and scale the work to the class; the Session policy sets the ceiling, the change sets the floor:

- `quick`: one reversible low-impact file; run one targeted check on the changed artifact; no Task record unless persistence matters.
- `standard`: focused test for the changed unit plus a regression check of adjacent behavior; record changed files and the verification command with its result in the Task `verification`.
- `strict`: acceptance evidence bound to the covered artifacts, independent review by `vibe-reviewer` through the strict review gate, and a re-run after any covered artifact changes.

Re-classify whenever the change grows past its declared files or signals. Never use a `quick` classification to skip correctness checks; escalate as soon as a check fails or scope grows.

## Implementation Rules

1. Make the smallest coherent change that satisfies the task.
2. Preserve unrelated behavior.
3. Follow existing project conventions unless a recorded decision changes them.
4. Keep external dependencies behind a controlled boundary where practical.
5. Add or update tests alongside behavior.
6. Add observability for important failures and state transitions.
7. Avoid silent fallback that hides broken requirements.
8. Do not broaden scope merely because adjacent cleanup is attractive; note follow-up work instead.
9. When code reveals a business ambiguity, stop that branch, classify it, and return to `a-business-clarify` if needed.
10. When the implementation must diverge from the spec, record the decision (Task `decisions`) and update the spec before declaring completion.

## Incremental Validation

Run the narrowest useful checks after each meaningful slice, then broader checks before handoff:

- formatting/static analysis;
- focused unit/component tests;
- integration tests;
- regression tests;
- build/package checks;
- environment/hardware validation where applicable.

Record the exact commands and results in the Task `verification.checks`; record what could not be run in `verification.limitations`.

## Status Rules

Map progress onto the V2 Task state:

- implementing → `status: active`, `phase: implement`;
- cannot proceed without a dependency or decision → `status: blocked` with `blocker` filled, and the current Session's `current-session.md` updated;
- outputs exist but required evidence is incomplete → stay `phase: verify` with `verification.status` `failed` or `blocked` and the missing evidence named in `limitations`; never report this as done;
- all `doneWhen` conditions and verification passed (and, under strict, review verdict `go`) → `phase: complete`, `status: completed`.

## Outputs

Update the Task JSON (decisions, verification, next action), the current Session's `current-session.md` while work remains unfinished, and `.vibe/progress.md` only when the landed change is a durable project fact (milestone, decision, limitation). Report changed files, verification, and material limitations to the user.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
