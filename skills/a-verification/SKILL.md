---
name: a-verification
description: Verify implementation against atomic acceptance criteria using traceable tests and evidence, distinguish partial or environment-limited validation, and prevent unverified work from being marked complete.
license: MIT
compatibility: codex
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
