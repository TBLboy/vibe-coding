---
name: a-engineering-landing
description: "落地实现/实施改动 | Implement an approved engineering task with controlled scope, traceability to business logic, incremental validation, V2 Task updates, and explicit handling of deviations or newly discovered ambiguity."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Engineering Landing

## Mental model

Implement an authorized behavioral delta in a living system: correctness is new behavior plus preservation of unaffected contracts. A patch is not complete until it reaches production callers, handles relevant failures and has meaningful evidence. Do not turn analysis into edits.

## Before editing: authority and risk

Confirm scope/non-goals, rules, `doneWhen`, relevant spec and blocking dependencies/C decisions. Inspect existing diff/status; preserve unrelated user changes. For registered work, from prepare call `begin_implementation` with risk, or confirm already in implement (repair/resume); do not repeat the event in implement. Spikes are experimental.

Risk is a verification floor, not a mode ceiling: `quick` local reversible edits need targeted check; `standard` changed behavior and adjacent regression (real wiring when relevant); `strict` consequential public contracts, data/migration, safety/security/permissions, concurrency/critical failure or difficult rollback require bound evidence and Strict review. Under fast/balanced stop before strict-risk implementation, request explicit `/strict`, pause/cancel old work as appropriate and start a new strict Task. Reassess actual consequences, uncertainty and recovery as scope expands; file count alone is not risk. Never mutate frozen Policy. Register strict implementation before edits, even for small changes. Strict Tasks always require review; fast/balanced Tasks never invoke it. Skip unnecessary documents, not evidence.

## Controlled change

- **Reconstruct:** find actual callers, defaults/configuration, state/resource owners, effects and tests. Separate approved behavior, observed behavior and existing failures. A green baseline is not product authority.
- **Bound:** map affected contracts and capabilities as `add`, `modify`, `preserve`, `replace`, `remove` or `unknown` with owner and evidence. Include public consumers, defaults, errors, cleanup, persistence and operational assumptions. Every removed responsibility needs a replacement or authorized retirement; unknown external consumers remain unknown. A small change needs only inline reasoning, not another durable ledger.
- **Choose a complete slice:** trace rule → behavior → interface/wiring → implementation → test. Prefer existing extension points and smallest coherent solution; no disconnected stubs, unused interfaces, placeholder success or broad cleanup. For fragile retained behavior use characterization/contract checks before changing it when feasible; do not preserve known defects as requirements. Consider compatible expansion → migration → removal where justified; identify rollback or roll-forward for irreversible effects.
- **Implement and check:** follow local ownership, dependency direction and error contracts. Add focused behavior tests; run narrow checks and inspect the diff after meaningful slices. Verify real registration/configuration/entrypoint, failure, retries, timeout/cancellation and cleanup where relevant. Avoid silent fallbacks, swallowed exceptions, hardcoded environment assumptions and logging secrets. Do not deploy, push, migrate real data or use destructive Git operations without authority.
- **Reconcile:** forward trace changed rules to actual execution and evidence; backward start from old contracts and trace removed duties, callers, defaults and failure paths. Absence of references is not proof of absence of a contract. Inspect test/config changes and unrelated diff; unexplained losses are unresolved. See `references/change-method.md` for an optional preservation/slicing example.

## Discoveries and handoff

If code contradicts approved semantics, or a C decision (product, public interface, safety, data, cost, irreversible choice) emerges, stop affected work and clarify or revisit design. A local reversible choice is independent; B material recoverable deviations use `record_decision` in prepare/implement, with spec/evidence updated before proceeding. Materially changed goal/acceptance requires a new approved Task, not edits to registered criteria. Reassess risk; never weaken tests or broaden scope silently.

Use `a-verification` to select and execute final checks. For registered work bind artifacts with `begin_verification` before final checks, submit actual `verification_passed` or `verification_failed`; invalidate stale evidence, reverify after changes. Use `block` and recovery note when needed. Main Agent handles Strict authorization, Reviewer and close through `docs/03-STATE-MACHINE.md`; this Skill is not independent merge approval. Use `b-branch-engineering-review` only for separately requested branch audits.

Completion requires approved acceptance, production wiring, retained/authorized-retired behavior, fresh evidence and required review. Report changed behavior, meaningful decisions, evidence and limitations; update progress only for durable facts. When implementation changes a documented mechanism, reconcile the affected current technical knowledge and navigation references; preserve prior decisions/history and approved business rules. Do not claim a changed behavior is verified without current evidence.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
