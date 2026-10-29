---
name: a-business-code-align
description: "Audit and reconcile business logic, code implementation, configuration, and tests by building traceability, classifying mismatches, fixing safe defects, and escalating semantic conflicts without letting code silently redefine requirements."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Business–Code–Test Alignment

## Purpose

Determine whether the system specification, implementation, and executable evidence tell the same story.

## Sources

Inspect:

- confirmed and experimental business rules (`.vibe/requirements.md`, Task `doneWhen`, `AGENTS.md`);
- architecture constraints and recorded decisions (`.vibe/progress.md`, Task `decisions`);
- code and configuration;
- automated tests and fixtures;
- runtime evidence and known incidents;
- implementation/test references already recorded.

## Audit Directions

Perform both directions:

### Business → code/test

For each active rule:

- locate implementation paths;
- locate acceptance evidence;
- identify missing branches, failure handling, or invariants;
- verify that tests assert the business outcome rather than internal details only.

### Code/test → business

Identify externally observable behavior, persistent state changes, permissions, limits, fallbacks, and integration rules in code/tests that have no business rule.

## Finding Types

- `missing-implementation`: active business logic is absent or incomplete in code;
- `missing-test`: implementation exists but acceptance evidence is missing;
- `undocumented-behavior`: code exposes behavior not represented in business logic;
- `stale-business-logic`: strong evidence indicates the recorded rule is obsolete;
- `implementation-drift`: code partially diverges from the active rule;
- `test-drift`: tests encode behavior that conflicts with active logic;
- `traceability-gap`: behavior may align, but references/evidence are insufficient;
- `conflict`: authoritative sources disagree and the correct behavior cannot be determined autonomously.

## Decision authority

- **A**: reversible, local, low-impact — resolve directly.
- **B**: material but recoverable — resolve, then record it in the active Task JSON `decisions` (or `.vibe/progress.md` when it is a durable project fact).
- **C**: product semantics, safety, data, public interfaces, cost, or irreversible architecture — ask the user; one question, with a recommendation and its consequence.

## Default Actions

- Fix clear implementation/test defects when authority is A or B and scope is controlled.
- Add missing traceability references when supported by evidence.
- Do not automatically update active business logic because code differs.
- For undocumented behavior, determine whether it is an accidental bug, internal-only behavior, or a genuine missing requirement.
- For stale logic, require evidence and appropriate authority before superseding it.
- For conflict, raise a C-level question with recommendation and impact.

## Output

Report each finding with: type, severity, confidence, affected rules, code/tests, evidence, recommended action, authority, status, and resolution. Persist only the durable part: fixes applied go through normal verification in the Task; unresolved findings that block work go to Task `blocker`; findings that change what the project knows about itself (for example a confirmed stale rule) go to `.vibe/progress.md` or `.vibe/requirements.md`. Create a follow-up Task only for repairs that are not applied immediately and need persistent tracking.

## Completion Gate

- all in-scope rules have implementation and verification disposition;
- all material undocumented behaviors are classified;
- no critical conflict is hidden;
- resolved findings have evidence;
- remaining findings are assigned or explicitly accepted.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
