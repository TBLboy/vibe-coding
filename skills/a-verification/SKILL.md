---
name: a-verification
description: "验证方案/测试计划/怎么验证 | Verify implementation against atomic acceptance criteria using traceable tests and evidence, distinguish partial or environment-limited validation, and prevent unverified work from being marked complete."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Verification

## Mental model

Verification is a falsifiable argument about behavior, not a test count. A green check may observe the wrong subject, oracle, setup or environment. For each approved claim ask what could disprove it, and choose the lowest sufficient evidence layer; add real integration when wiring matters. No suite proves absence of every defect.

## Derive evidence

- **Claims:** use approved rules, `doneWhen`, invariants, spec, diff and affected callers. Include intended outcomes, prohibited effects and retained behavior. Current code/tests are not the sole specification; surface conflicts.
- **Subject:** trace actual production ingress, config/registration, dependency injection, state and effects. Unit tests cover local logic; component tests real ownership; integration/contract tests real wiring; E2E user journeys; representative environment/hardware actual operational assumptions. Mock only dependencies not under test; a mock must not hide the claimed behavior.
- **Independent oracle:** derive expected outputs/state, effects and absence of effects, errors, timing/tolerance or invariants from authority before reading implementation outputs. Use deterministic fixtures/clocks/seeds where relevant. A non-crash, import, log or mock invocation alone is insufficient unless that is the claim.
- **Adequacy:** inspect collection, invocation, assertions, preconditions and mocks. For consequential claims use a safe counterexample where feasible: known failing baseline, isolated reversible mutation/fault or independently derived result. Confirm intended failure reason, remove mutants; never mutate production. Document when not feasible. Do not equate coverage/line count with correctness.

## Select tests by failure mechanism

| Risk signal | Method |
|---|---|
| Constraints / invalid input | partitions, below/at/above boundaries, empty/malformed; reject without unintended effects |
| Lifecycle / protocol / permissions | legal/illegal, terminal, duplicate and out-of-order transitions through real ingress; persisted state and effects |
| API / configuration / wiring | consumer/provider semantic contract, actual route/defaults/registration, old consumers |
| Refactor / removal | characterize approved old behavior; differential new/old results including errors, not known bugs |
| Retry / concurrency / transaction | fault injection, deterministic scheduling/clock, partial failure, duplicate/interleaved requests, cleanup and recovery; avoid sleep-only evidence |
| Transformation invariants | property/metamorphic checks, reproducible seeds, known examples and independent oracle |
| Migration / performance / hardware | representative data/environment, old/new compatibility, rollback; workload baseline, distribution/threshold and repeated samples when performance matters |

Use risk-based or pairwise combinations when state space grows; name uncovered critical interactions. See `references/test-design.md` for a worked green-suite/production-bypass example. Keep a concise mapping of rule/claim, failure hypothesis, target/layer, fixture, oracle, command, result and limitations; reuse spec for larger work, no separate document by ritual.

## Execute and assess

`quick`: targeted check/read-back; `standard`: behavior plus adjacent regression, integration when boundary changes; `strict`: bound acceptance evidence and required representative environment plus independent review. Effective Policy and risk govern depth, not file count; fast/balanced may verify standard work deeply but cannot run strict-risk implementation or invoke Reviewer. All registered strict Tasks require review even for quick work; ordinary consultation without tracking needs does not. Main Agent owns reviewer gate.

Exploratory checks may run during implementation. For registered Tasks use `begin_verification` with explicit covered relative artifacts **before final checks** from implement (include relevant unchanged files, requirements, fixtures/harness, configs, locks). Runtime covers Git changes too; ignored/external dependencies/services/hardware need separate evidence. Digest proves freshness, not execution.

Capture exact command/exit, relevant output, claims covered, environment and limitations. Inspect failures, collection, skips, truncated output and flaky retries. Do not count skipped/uncollected cases as passes. Diagnose failures as implementation, test/oracle, requirement, environment or harness using the smallest discriminating check; never adjust assertions/requirements just to turn tests green. Repair only when authorized. If inputs change after verification starts use `invalidate_verification` and re-enter final verification from implement.

## Evidence and completion

Distinguish observed pass/fail, inferred, not run and justified N/A. Static inspection establishes structure, not runtime outcomes; representative manual/visual/hardware checks can be valid evidence. If environment/credentials/data are missing, do valid lower-level checks and report precisely what remains unknown. Essential unverified criteria require `verification_failed` or `block`; N/A only when the usual check genuinely does not apply and relevant alternative inspection was performed. Never claim missing environment passed.

Submit through Runtime `verification_passed` (or `status: not_applicable` with `notApplicableReason`) / `verification_failed` with exact checks, summary and limitations; follow `docs/03-STATE-MACHINE.md`. Strict pending review is not completion. No direct Task JSON edits or invented review events. Complete only when essential claims and retained behavior have current relevant evidence, failures/skips/limitations are explicit and required review is handled by Main Agent. Report what evidence would still falsify the claim. Consult relevant indexed lessons for previously missed failure mechanisms; check applicability rather than reusing old test results. Persist only future-useful validation findings, with subject, revision/configuration, scope and limitations, in the existing Task or appropriate durable knowledge; update material limitations when resolved.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
