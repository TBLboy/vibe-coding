---
name: a-engineering-landing
description: "落地实现/实施改动 | Implement an approved engineering task with controlled scope, traceability to business logic, incremental validation, V2 Task updates, and explicit handling of deviations or newly discovered ambiguity."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Engineering Landing

## Purpose and mental model

Implement an approved task as a controlled change to a living system. Correctness is the new capability **plus** preservation of unrelated existing contracts. The unit of change is a coherent behavioral delta, not a file or line count. A small patch can be high impact; a large deletion can be correct when its responsibilities are accounted for.

## Before Editing

Confirm approved rules, non-goals, `doneWhen`, blocking dependencies and required C decisions. Read the relevant spec for non-trivial work (`a-engineering-spec`). A registered Task must be active; from `prepare` use `begin_implementation` with declared risk before edits, or confirm it is already in `implement` with its frozen policy. Do not call that event again in `implement` (e.g. repair/resume). Explicitly labeled spikes are experimental, not production completion.

## Risk routing

Risk sets the verification floor independently of mode:

- `quick`: reversible local low-impact edit; targeted check/read-back; Task only when policy warrants it.
- `standard`: changed behavior plus adjacent regression, exact commands/results and material decisions in the Task when registered.
- `strict`: consequential public contract, destructive data or migration, safety/security/permissions, concurrency or critical failure paths, or difficult rollback; bind acceptance evidence and use independent strict review. Classify by consequences, not line count.

Strict risk under fast/balanced: stop before further implementation, request explicit `/strict`, pause/cancel the old Task as appropriate and start a new strict Task; never change frozen policy. Reassess risk when affected behavior, dependencies or uncertainty expands. Fast/balanced may run deeper tests, but cannot invoke Reviewer. Strict policy always requires review even for a low-risk change.

## Analysis method: reconstruct → bound → implement → reconcile

1. **Reconstruct before touching.** Locate actual production callers, configuration/defaults, state and resource owners, tests and dependent entrypoints for the target behavior. Inspect the current diff/status without overwriting unrelated work. Identify approved vs observed behavior, including error paths and implicit contracts. A green baseline is useful but not proof of intended behavior; capture existing failures separately.
2. **Make a change/preservation ledger.** For affected abilities and contracts, classify `add`, `modify`, `preserve`, `replace`, `remove`, or `unknown`; map current code/callers to planned owner and regression evidence. Include public imports, config defaults, failure/cleanup, persistence, side effects, operational constraints and external consumers where relevant. Every removed responsibility needs a replacement or justified authorized retirement. Unknown external users remain unknown. A local edit needs only a short mental/inline ledger; do not create another durable artifact.
3. **Choose the smallest complete delta.** Trace requirement → behavior → interface/wiring → implementation → test. Inspect existing extension points before adding abstractions. A complete slice covers implementation, actual registration/routing/configuration, error behavior, and necessary tests/docs. Do not land unused interfaces, placeholder success, or unconnected code as finished. Avoid broad cleanup; if a shared change is essential, map its consumers and explain the coupling. Escalate unapproved semantic, public-contract or irreversible changes through the existing C authority.
4. **Protect baseline and stage the change.** Add characterization/contract tests for fragile retained behavior when feasible before refactoring, or record an equivalent baseline check. Do not enshrine a known bug as an approved rule. Prefer independent reversible slices; when changing a shared API/data contract, consider compatible expansion, consumer migration, then removal only after evidence and approval. Plan rollback or roll-forward for irreversible effects. Do not use destructive Git commands or touch unrelated dirty files.
5. **Implement and check each slice.** Follow local conventions, dependency direction, ownership and error contracts. Add focused behavior tests alongside code. Run narrow checks after meaningful slices, inspect the actual diff, and trace at least one real entrypoint. Preserve behavior on failures, timeout/cancellation, cleanup and retries where relevant. Avoid silent fallback, hardcoded environment assumptions, swallowed exceptions or tests that only assert a helper's existence. Log meaningful failures without leaking sensitive data.
6. **Handle discoveries explicitly.** If code disagrees with approved requirements or introduces a new C decision, stop the affected path and use `a-business-clarify` or `a-architecture-decision`. For a material recoverable spec deviation, record the B decision through Runtime, update existing spec and acceptance evidence before proceeding. Reassess risk and impact; do not silently broaden the task, redefine requirements, weaken tests or change mode. Preserve unrelated user edits.
7. **Reconcile forward and backward.** Forward: show each new/changed rule reaches production via real call paths, including failures and required integration. Backward: revisit the preservation ledger from the original behavior rather than the new implementation; trace removed responsibilities, affected callers, old defaults and regressions. Classify unexplained losses as unresolved, not as incidental cleanup. Inspect actual changes against non-goals, including changes to tests/configuration. If material unknowns remain, do not report complete.
8. **Handoff to verification.** Select checks via `a-verification`, bind covered artifacts before final checks using Runtime, and report exact results, changed files, preserved/retired capabilities and gaps. Use `b-branch-engineering-review` for a separate branch audit when requested; this Skill is implementation-time protection, not independent merge approval.

## Decision rules and anti-patterns

- A reversible local implementation decision may be made directly; B material recoverable decisions are recorded; C product semantics, public interface, safety, data, cost or irreversible choices require user approval. Follow the Agent contract.
- Prefer a coherent end-to-end slice over separate disconnected stubs; prefer a narrow adapter over widespread vendor-specific branching if it demonstrably isolates change.
- Deletion is not inherently bad; absence of references is not proof of absence of a contract. Avoid accidental cleanup, feature-driven framework rewrites, default changes disguised as refactors and false compatibility claims.
- Do not silently undo the user's existing work, auto-migrate real data, deploy, push or perform external side effects beyond authorization. Use isolated test environments.

For a material refactor or contract change consult `references/change-method.md` for a worked preservation ledger and slicing example.

## Status and outputs

During implement, use Runtime `record_decision` for registered Task decisions. If blocked, `block` and update the current Session recovery note. Run exploratory checks during implement; before final checks call `begin_verification` with covered artifacts, then submit `verification_passed` or `verification_failed` as specified in `docs/03-STATE-MACHINE.md`. If covered files/requirements/tests change, invalidate and re-run. Do not send a failed/missing required check as passed. Strict review is Runtime-owned; follow the Agent contract for authorization, repairs, and close. No direct Task JSON edits or invented lifecycle events.

Completion requires all approved acceptance criteria, production wiring, preserved/approved-retired behavior, relevant regression and fresh evidence, and strict review when required. Report what changed, why, verification, and material limitations. Update `.vibe/progress.md` only for durable project facts.

## V2 operating rules

- For registered Tasks, use Runtime lifecycle events in `docs/03-STATE-MACHINE.md`; never edit Task JSON directly.

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
