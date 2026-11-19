---
name: a-verification
description: "验证方案/测试计划/怎么验证 | Verify implementation against atomic acceptance criteria using traceable tests and evidence, distinguish partial or environment-limited validation, and prevent unverified work from being marked complete."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Verification

## Purpose and mental model

Verification is a falsifiable argument about behavior, not the count of passing tests. A test can pass while the real system is broken if its subject, oracle, setup or environment is wrong. For each approved claim identify what could disprove it and choose evidence capable of observing that failure. Verification does not prove absence of every defect.

## Analysis procedure

1. **Derive claims from authority.** Read approved rules and Task `doneWhen`, invariants, spec, change ledger/diff and affected callers. Map positive outcomes, prohibited outcomes and retained behavior. Do not treat current implementation or existing tests as the sole specification. When they conflict with an approved rule, isolate the conflict and seek appropriate authority.
2. **Identify the actual system under test.** Trace the production entrypoint, configuration/registration, dependency injection and side effects. Select a test layer that would fail if the suspected defect existed. Unit tests establish local logic; component tests cover a real owner and state; contract/integration tests cover real wiring and boundaries; end-to-end checks cover critical user-visible journeys; environment/hardware checks cover actual operational assumptions. A mocked dependency must not hide the behavior being tested. Prefer the lowest sufficient layer plus an integration check when wiring matters; not every task needs E2E.
3. **Construct an independent oracle.** Specify observable expected outputs, state, side effects, errors, absence of effects, time bounds or invariants from the requirement before reading expected values out of the implementation. Use deterministic fixtures, controlled clocks, known seeds/tolerances and preconditions as needed. Assertions must discriminate correct from wrong behavior; a non-crash, import, log or mock call alone is insufficient unless that is the actual claim.
4. **Generate cases based on failure mechanisms.** Choose methods below according to affected contracts/risk, not an exhaustive checklist for every change. Include negative paths and boundaries that could violate important invariants. Cover the new capability and preserved adjacent behavior. If refactoring, compare against the baseline for unchanged contracts; do not preserve known defects as requirements.
5. **Check test adequacy.** Trace test invocation to production target, inspect assertions, fixtures/mocks and runner collection. For consequential claims use a controlled counterexample when safe (known failing baseline, temporary reversible mutation in an isolated copy, deliberate fault, or independently derived expected result). Verify it fails for the intended reason, not setup. Never mutate a real production environment or leave a mutant in the deliverable. Record if not performed and why; a mutation is supporting evidence, not universally required.
6. **Execute and assess evidence.** Use focused checks during implementation, then begin bound final verification before executing the final checks. Capture exact command, result/exit, relevant output/coverage of claims, environment and limitations. Inspect failures, skips, collection, flaky retries and truncated logs. Do not count a skipped or uncollected case as passing. If performance matters measure in representative workload/environment with a baseline, distribution/threshold and repeated samples; do not infer hardware results from mocks.
7. **Diagnose failures before repair.** Classify implementation, test/oracle, requirement, environment or harness using reproduction and smallest discriminating check. Do not change assertions or requirements simply to make tests green. Repair through `a-engineering-landing` when authorized; invalidate evidence after changes and re-run affected checks. Report unmet essential criteria as failed/blocked, not partial success as completion.

## Test design techniques

| Signal in the change | Method and evidence |
|---|---|
| Input constraints, ranges, invalid values | Equivalence partitions and boundary values (below/at/above threshold, empty/malformed when relevant); assert rejection and no unintended side effect. |
| Lifecycle, permissions, protocol | State transition matrix: legal and illegal edges, initial/terminal, repeated/out-of-order events; drive real ingress and assert persisted state and effects. |
| Cross-module API/config/registration | Consumer/provider contract and production integration; exercise real route, defaults, data shape, semantic failures, and old consumers. |
| Refactor/deletion | Characterization tests before change, differential old/new runs on retained observable behavior; distinguish approved changes from regressions. |
| Retries, timeout, cancellation, concurrency, transactions | Fault injection, deterministic scheduling/clock where practical, duplicate and interleaved calls, partial write/cleanup, idempotency and recovery; avoid relying solely on sleep. |
| Invariant-heavy transformations | Property or metamorphic tests with known examples, reproducible seeds and failing inputs; independent oracle where feasible. |
| Migration, dependencies, operational constraints | Representative fixtures/environment, old/new version compatibility, realistic data and rollback/roll-forward, load/hardware probes where essential. |

Use pairwise/risk-based combinations when the state space grows; document uncovered critical interactions. For test selection and an example of a green unit suite with a broken production entrypoint, see `references/test-design.md`.

## Verification Matrix

For each affected criterion or retained contract map: ID/rule, observable claim and failure hypothesis, target/production path, layer/method, fixture/preconditions, expected oracle, exact test/command, result and evidence, limitations. Use a few inline rows for ordinary work; reuse the existing spec for larger work if needed. No mandatory extra document.

## Depth by risk and policy

- `quick`: one relevant targeted check or read-back of the changed artifact, with exact command/inspection and observation.
- `standard`: focused behavior test plus adjacent regression; real integration when wiring or a boundary changes.
- `strict`: acceptance evidence bound to covered artifacts, required representative environment checks, independent `vibe-reviewer` through the strict gate, and re-verification after relevant changes.

Risk is a floor, not a mode ceiling; fast/balanced cannot run strict-risk implementation or invoke Reviewer. Strict mode requires independent review regardless of risk. Verification depth follows the actual claim, not the number of files.

## Evidence and limitations

Match evidence to the claim: representative automated acceptance/integration is strong for wiring; focused tests are strong for isolated logic; reproducible manual/scripted checks can be appropriate for visual or hardware behavior; static reasoning is evidence of structure, not runtime outcomes. Do not rank an irrelevant E2E test above a relevant unit test. Distinguish observed pass/fail, inferred, not run and justified N/A. For missing hardware, credentials, external dependencies or representative data, run valid lower-level checks and state exactly what remains unknown. If an essential claim remains unverified, use `verification_failed` or `block`. A justified `not_applicable` is only for work where the usual check does not apply and a relevant alternative inspection was performed, not an escape from a missing required test. Never claim an unavailable environment passed.

## Runtime and output

For registered Tasks call `transition/begin_verification` from implement BEFORE final checks with explicit covered relative artifacts (including relevant unchanged files, requirements, fixtures/harness, configs and dependency locks). Runtime also covers Git changes; ignored dependencies/external services and hardware require separate evidence. Artifact digest proves freshness, not that tests were executed. Submit through `verification_passed` (or justified `status: not_applicable` with `notApplicableReason`), or `verification_failed` with summary, exact checks/results and limitations. Use `invalidate_verification` if inputs change after verification starts; then re-enter final verification from implement. Do not directly edit Task JSON, bypass strict Reviewer or treat pending review as complete. See `docs/03-STATE-MACHINE.md`.

## Completion gate and anti-patterns

Every essential claim has relevant current evidence; test layer and oracle match the failure risk; affected retained behavior is checked; failures/skips/limitations are explicit; strict review and close are handled by Runtime. Avoid line-count/coverage-as-proof, tautological tests, mocking the integration under test, snapshot updates without contract analysis, retries hiding flakes, and using stale evidence or passing unrelated suites as proof. Report the evidence and what would still falsify the claim; do not claim total correctness.

## V2 operating rules

- For registered Tasks, use Runtime lifecycle events in `docs/03-STATE-MACHINE.md`; never edit Task JSON directly.

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
