---
name: a-verification
description: "Verify implementation against atomic acceptance criteria using traceable tests and evidence, distinguish partial or environment-limited validation, and prevent unverified work from being marked complete."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Verification

## Purpose

Prove that the implementation satisfies the business requirement rather than merely compiling or passing unrelated tests.

## Verification Matrix

For every affected business rule and acceptance criterion (Task `doneWhen`), map:

- expected observable behavior;
- verification method;
- environment and preconditions;
- command/test/manual procedure;
- evidence location;
- result;
- limitations.

## Depth by risk class

Match the verification depth to the change's risk and the Task's frozen policy instead of applying one weight everywhere:

- `quick`: one targeted check or read-back of the changed artifact, recorded with its exact command or inspection.
- `standard`: focused test plus adjacent regression; the evidence must name the unit it covers.
- `strict`: acceptance evidence bound to the covered artifacts, independent review by `vibe-reviewer` that does not reuse the implementer's conclusions, and a re-run after those artifacts change.

Never treat a truncated read, a partial log, or a skipped suite as complete evidence; read the blocking fact directly.

## Evidence Levels

From strongest to weakest:

1. automated acceptance/integration test in a representative environment;
2. focused automated unit/component test plus supporting integration evidence;
3. reproducible scripted/manual validation;
4. inspection or static reasoning only.

Do not describe level 4 as full verification.

## Checks

- happy path;
- failure and boundary behavior;
- state transitions and side effects;
- permissions/security where relevant;
- data migration/compatibility;
- concurrency, retries, timeout, and idempotency where relevant;
- regression of adjacent critical behavior;
- operational visibility.

## Handling Limitations

If hardware, credentials, production data, external services, or environment access are unavailable:

- run all possible lower-level checks;
- mark the exact missing evidence in `verification.limitations`;
- keep `verification.status` at `failed` or `blocked` (not `passed`), and do not move the Task to `complete`;
- when no automated check applies at all, use `not_applicable` with an explicit `notApplicableReason` and perform the best relevant manual check;
- create a focused follow-up validation Task only if it needs persistent tracking.

## Outputs

Update the Task `verification` object (`status`, `summary`, `checks` with exact commands and results, `limitations`). Report the same to the user. Do not modify business rules to make failing implementation appear correct.

Evidence is tied to the artifacts it covered: if covered files, requirements, dependencies, or the verification harness change afterwards, the previous result is stale and must be re-run before completion.

When verification fails, classify the origin before selecting the next action — implementation, test, requirement, environment, or harness. A failed test is not sufficient evidence that the origin is implementation.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
