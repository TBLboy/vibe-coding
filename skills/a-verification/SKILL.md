---
name: a-verification
description: Verify implementation against atomic acceptance criteria using traceable tests and evidence, distinguish partial or environment-limited validation, and prevent unverified work from being marked complete.
license: MIT
compatibility: opencode
metadata:
  stage: verification
  output: acceptance-evidence
---

# Verification

## Purpose

Prove that the implementation satisfies the business requirement rather than merely compiling or passing unrelated tests.

## Verification Matrix

For every affected business atom and acceptance criterion, map:

- expected observable behavior;
- verification method;
- environment and preconditions;
- command/test/manual procedure;
- evidence location;
- result;
- limitations.

## Depth by risk class

Match the verification depth to the task's routing class instead of applying one weight everywhere:

- `quick`: one targeted check or read-back of the changed artifact, recorded with its exact command or inspection.
- `standard`: focused test plus adjacent regression; the evidence must name the unit it covers.
- `strict`: acceptance evidence bound to the covered artifacts, independent review that does not reuse the implementer's conclusions, and a re-run after those artifacts change.

Budget limits apply to context packages, never to blocking facts: when `state-context` reports `budget_insufficient`, raise the budget or read the blocker directly. Do not treat a truncated package as complete.

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
- mark the exact missing evidence;
- keep status `implemented-unverified` or verification `partial`;
- create a focused follow-up validation task.

## Outputs

Update task verification, acceptance evidence in business atoms, and current session. Do not modify business rules to make failing implementation appear correct.

Register durable evidence in `.project-log/loop/evidence-index.yaml` through `loopctl record-evidence`. Bind it to the current Git commit/diff or covered file hashes. Later changes to covered files, requirements, dependencies, or the verification harness must mark the evidence `stale`.

When verification fails, classify the origin before selecting the next action. A failed test is not sufficient evidence that the origin is `implementation`.
