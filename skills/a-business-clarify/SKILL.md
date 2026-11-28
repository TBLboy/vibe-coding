---
name: a-business-clarify
description: "业务澄清/需求澄清/规则不清楚 | Clarify vague business intent into atomic, testable business logic through active evidence gathering, focused clarification, controlled inference, and durable V2 memory updates."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Business Clarify

## Mental model

Clarification builds an accurate model of what the product should mean and do, not a questionnaire or a technical solution. Ground it in the actual user's goals, actors, habits, existing tools, constraints and non-goals. Read relevant user statements, AGENTS.md, active requirements (via index), Task/Session context, code, configuration, tests and historical decisions before asking for facts already obtainable.

## Establish and reconcile business logic

- **Fact map:** classify material claims as `confirmed`, `evidence-derived`, `inferred`, `unknown`, `conflict` or `out-of-scope`. Current code is evidence of behavior, not automatic business authority. Never promote inference to confirmation silently.
- **Functional view:** actors/permissions, triggers, preconditions, normal and exceptional flows, state transitions, inputs/outputs, effects, invariants, boundary/repeat/concurrency/idempotency semantics, ownership/visibility/retention. Select relevant dimensions, not an exhaustive form.
- **Technical view:** trace how existing code, configuration, interfaces, state, transactions, dependencies and deployment constraints carry that behavior. Identify conflicts among implementation, tests and authoritative rules. Do not choose future libraries or architecture here.
- **Alignment:** mark material differences as `confirmed-match`, `missing-implementation`, `implementation-drift`, `missing-test`, `test-drift`, `constraint-conflict` or `unknown`. A full bidirectional audit belongs to `a-business-code-align` when needed.
- **Product reasoning:** when asked for analysis, present a coherent assessment and recommendations with evidence, benefits, costs, tradeoffs and assumptions. Check whether existing tools or user practices already solve the problem before proposing a feature. Do not extrapolate beyond the actual usage scenario.
- **Controlled derivation:** infer necessary consequences of confirmed rules and existing constraints (e.g. importing existing logs cannot silently replace their contents). State premises and reasoning; distinguish logically required integrity/observable behavior from optional conveniences or technical alternatives. Escalate material C decisions rather than assuming approval.

## Atomic rules and clarification

An atom is one independently judgeable behavior, transition, constraint or integration rule. Split when parts can fail, change or be accepted independently. Capture actor/trigger, preconditions, inputs, rule, effects, failure/invariants, observable acceptance (Given–When–Then where useful), and source/authority. Scale to actual complexity.

Resolve A reversible local decisions directly; record B material recoverable decisions through Runtime `record_decision` or durable `.vibe/progress.md`; C product semantics, public interfaces, safety, data, cost or irreversible architecture require user authority. When a material blocker remains, rank by business impact × uncertainty × rework cost, then ask one highest-value question with recommendation, reason and consequence (safe default only if real). Do not force a one-question loop when the user invites a holistic review. A user may correct or add information at any time.

Treat feedback as a revision of the whole model: retain accepted rules, replace corrected ones, discard rejected proposals, separate deferred ones; invalidate affected assumptions and downstream decisions/tasks before selecting the next question. Do not reopen settled decisions without new evidence.

Use `a-deep-research` only if technical feasibility, platform/hardware, latency, licensing, cost/privacy or other constraints materially change possible business behavior, or the user requests it. Ordinary technical preferences do not require research during clarification.

## Output and authority boundary

Return consolidated goal, use context, confirmed/changed/rejected rules, necessary implications, observable acceptance, non-goals and blocking/non-blocking questions. Draft/inferred rules remain labeled. Use `a-requirement-baseline` for durable business rules; no separate file for small work by ritual. Set Task `goal`/`doneWhen` before registration. After registration, never rewrite them: clarify the impact, use `record_decision` for compatible refinements in prepare/implement, and if acceptance/scope materially changes, follow the supersession rule in `docs/06-AGENT-CONTRACT.md` and start a new Task with the approved criteria under the current Session policy. Use `block` for unresolved blocking C decisions and the Session recovery note when needed. Follow `docs/03-STATE-MACHINE.md`.

Completion: relevant happy paths, material exceptions, permissions and invariants are covered; technical facts/conflicts are investigated; no blocking C question remains for implementation; in-scope atoms are observable or explicitly unresolved; low-impact unknowns are deferred or assigned to research. Clarification eliminates expensive hidden assumptions, not every possible unknown.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
