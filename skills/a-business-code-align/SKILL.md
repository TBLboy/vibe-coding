---
name: a-business-code-align
description: Audit and reconcile business logic, code implementation, configuration, and tests by building traceability, classifying mismatches, fixing safe defects, and escalating semantic conflicts without letting code silently redefine requirements.
license: MIT
compatibility: codex
metadata:
  stage: alignment
  output: alignment-findings
---

# Business–Code–Test Alignment

## Purpose

Determine whether the system specification, implementation, and executable evidence tell the same story.

## Sources

Inspect:

- active and experimental business atoms;
- requirement baseline;
- architecture and decision records;
- code and configuration;
- automated tests and fixtures;
- runtime evidence and known incidents;
- implementation/test references already recorded.

## Audit Directions

Perform both directions:

### Business → code/test

For each active atom:

- locate implementation paths;
- locate acceptance evidence;
- identify missing branches, failure handling, or invariants;
- verify that tests assert the business outcome rather than internal details only.

### Code/test → business

Identify externally observable behavior, persistent state changes, permissions, limits, fallbacks, and integration rules in code/tests that have no business atom.

## Finding Types

- `missing-implementation`: active business logic is absent or incomplete in code;
- `missing-test`: implementation exists but acceptance evidence is missing;
- `undocumented-behavior`: code exposes behavior not represented in business logic;
- `stale-business-logic`: strong evidence indicates the recorded rule is obsolete;
- `implementation-drift`: code partially diverges from the active rule;
- `test-drift`: tests encode behavior that conflicts with active logic;
- `traceability-gap`: behavior may align, but references/evidence are insufficient;
- `conflict`: authoritative sources disagree and the correct behavior cannot be determined autonomously.

## Default Actions

- Fix clear implementation/test defects when authority is A or B and scope is controlled.
- Add missing traceability references when supported by evidence.
- Do not automatically update active business logic because code differs.
- For undocumented behavior, determine whether it is an accidental bug, internal-only behavior, or a genuine missing requirement.
- For stale logic, require evidence and appropriate authority before superseding it.
- For conflict, create a C-level question with recommendation and impact.

## Output

Write `.project-log/alignment/findings.yaml`, create repair tasks, and update references in atoms/tasks after verified fixes.

Each finding must include severity, confidence, affected atoms, code/tests, evidence, recommended action, authority, status, and resolution.

## Completion Gate

- all in-scope atoms have implementation and verification disposition;
- all material undocumented behaviors are classified;
- no critical conflict is hidden;
- resolved findings have evidence;
- remaining findings are assigned or explicitly accepted.
