---
name: a-architecture-decision
description: "架构决策/模块划分/接口与失败边界 | Convert an approved requirement baseline and technical recommendation into explicit module boundaries, interfaces, data flows, failure handling, operational constraints, and recorded architecture decisions."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Architecture Decision

## Purpose and mental model

Architecture is the set of consequential choices that determines where responsibilities, state, dependencies and failure boundaries live. Derive it from the current system and approved needs, not from a preferred pattern or a blank-sheet diagram. Optimize for the next real change while preserving constraints; a smaller extension can be better architecture than a general framework.

## Inputs

- Approved requirement baseline (`.vibe/requirements/<work>.md` when present, otherwise confirmed Task `goal`/`doneWhen`), atomic rules and non-goals.
- Existing code, entrypoints, configuration, tests, deployment constraints and recorded decisions (`.vibe/progress.md`, active Task).
- Research results from `a-deep-research` when a technical assumption needs evidence. Unknowns are not requirements.

## Analysis and decision procedure

1. **Reconstruct the current system.** Trace at least the relevant production entrypoint through callers, modules and external effects; inspect dependency direction, state ownership, lifecycle and failure paths. Identify public and implicit contracts. Distinguish observed behavior from intended rules and unresolved conflicts. Use `a-codebase-onboarding` if context is insufficient.
2. **Extract architectural drivers.** Map approved rules to functional responsibilities and invariants (what must always hold). For material quality attributes express a concrete scenario: stimulus + environment + affected component + expected response + measurable criterion. Separate hard constraints from preferences; do not invent a latency target, SLA or future feature. Rank drivers by consequences and uncertainty, with user authority for material new constraints.
3. **Find boundaries from change and ownership.** Group code that changes for the same reason or enforces the same invariant; hide decisions likely to change behind stable contracts. Put each mutable state and invariant under an identifiable owner; callers use the owner's interface rather than duplicate state or bypass it. Draw dependencies and runtime flow separately. Keep dependency cycles, infrastructure leakage, cross-boundary transactions and failure propagation visible. Introduce a port/adapter only when it isolates a concrete dependency or meaningful variation; do not default to layers, plugins or services.
4. **Generate feasible alternatives.** For consequential decisions compare the current architecture/minimal extension with at least one credible alternative when available (e.g., local composition vs strategy interface, shared process vs separate service). Include doing nothing/defer when it meets the requirement. If only one option is viable, identify the disqualifying constraints rather than inventing alternatives. Reject options violating hard invariants before trading preferences.
5. **Evaluate tradeoffs.** For each viable option connect a concrete driver to a mechanism and its consequences: correctness, change locality, coupling, latency/resources, fault containment, security, operational burden, testability, migration and reversibility. Name the worst plausible failure and a way to detect it. Rank by actual constraints, not generic numerical scores. Distinguish proven facts from estimates; use a time-bounded spike for a high-impact uncertainty (hypothesis, method, success criterion, stop condition); do not present a successful toy POC as production evidence.
6. **Specify the chosen design.** Describe the before/after delta and its why, ownership, dependencies, contracts, state and error behavior. For a boundary specify caller/owner, valid inputs and outputs, semantic guarantees, failure/timeout/retry and lifecycle as relevant. Trace critical success and failure scenarios end-to-end, including partial failures and cleanup. If a public contract changes, specify consumers, migration sequence, compatibility window and rollback/data implications; prefer expand → migrate → contract when needed, not as mandatory ceremony.
7. **Challenge and hand off.** Ask what existing capability is lost, who owns each invariant, what happens during deployment/rollback and which proposed abstraction has no real consumer. Identify the smallest independently verifiable slices and the tests/probes that would falsify key assumptions. Resolve A/B choices, escalate C choices before implementation. Feed the chosen constraints and testable outcomes into `a-engineering-spec` / `a-task-decompose` as appropriate; do not implement while authority or essential feasibility is unresolved.

## Required Views

Cover affected views at the minimum useful depth; explicitly identify critical unaffected constraints, not a boilerplate architecture document:

1. Responsibilities and ownership — modules/services/nodes, invariants and change reasons.
2. Interfaces — APIs, events, topics, actions, files, schemas or device boundaries, including semantic contracts.
3. Data flow — source, transformation, ownership, persistence and destination.
4. State and concurrency — lifecycle, synchronization, transactions, retries, idempotency.
5. Failure behavior — detection, containment, recovery, user-visible outcome and cleanup.
6. Security and privacy — trust boundaries, permissions, secrets, sensitive data.
7. Observability — signals that diagnose violations and measure the important scenarios.
8. Deployment and compatibility — versions, environment, hardware, migration and rollback.

## Decision authority

- **A**: reversible, local, low-impact — resolve directly.
- **B**: material but recoverable — resolve and record through Task `record_decision` (or `.vibe/progress.md` for a durable project fact).
- **C**: product semantics, safety, data, public interfaces, cost or irreversible architecture — ask the user; one focused question with recommendation and consequences. No option comparison can authorize C on its own.

For B/C decisions use a concise decision record: context/rule, options and rejected alternative, chosen rationale, tradeoffs, assumptions/evidence, migration/rollback or conditions for revisiting, authority/approval. A proposed decision is not an approved one. Follow `docs/06-AGENT-CONTRACT.md` and Runtime events in `docs/03-STATE-MACHINE.md`.

## Anti-patterns and checks

- Pattern-first design, architecture diagrams with no execution or state ownership, abstractions for hypothetical consumers, implicit changes to product semantics.
- Choosing by benchmark alone without workload/environment match; hiding migration, failure or operational costs; claiming a dependency works because its documentation says so.
- Splitting an invariant across independent writers, treating an interface signature as a full contract, making a new layer for every noun.

For material design, consult `references/decision-method.md` for a worked tradeoff and failure-path example. Use the same reasoning in a few sentences for local reversible choices; no new Task/file/stage is required just to use this Skill.

## Output and completion gate

Return a concise baseline with the current/target delta, drivers, selected option and alternatives, affected views, verification implications and open decisions. Persist only material decisions and durable constraints in existing V2 locations. Completion means ownership and dependency direction are clear, critical paths and contracts have explicit owners, tradeoffs are tied to approved needs, material assumptions are validated or named as blockers, C choices are approved, and a competent implementer need not invent product behavior. This is design completion, not implementation acceptance.

## V2 operating rules

- For registered Tasks, use Runtime lifecycle events in `docs/03-STATE-MACHINE.md`; never edit Task JSON directly.

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
