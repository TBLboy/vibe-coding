---
name: a-architecture-decision
description: "架构决策/模块划分/接口与失败边界 | Convert an approved requirement baseline and technical recommendation into explicit module boundaries, interfaces, data flows, failure handling, operational constraints, and recorded architecture decisions."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Architecture Decision

## Mental model

Architecture allocates responsibility, state, dependencies and failure boundaries to satisfy actual system constraints. Begin with the existing architecture and approved needs, not a preferred pattern. Optimize for the next real change; preserve sound boundaries and avoid hypothetical extensibility.

## Derive the design

- **Reconstruct:** trace relevant production entrypoints, callers, configuration, external effects, state owners and failure paths. Separate intended contracts, observed behavior and unknowns. Use `a-codebase-onboarding` only if more system context is needed.
- **Identify drivers:** derive responsibilities and invariants from approved rules (`.vibe/requirements/<work>.md` or confirmed `goal`/`doneWhen`). For material quality attributes specify stimulus, environment, affected component, response and measurable criterion. Separate hard constraints from preferences; do not invent budgets, SLAs or future features.
- **Choose boundaries:** group responsibilities by invariants and reasons for change; hide volatile decisions behind stable contracts. Assign each mutable state/invariant an identifiable owner and write path; callers must not bypass the owner. Trace static dependencies separately from runtime data flow. Expose cycles, transaction boundaries and failure propagation. Add ports/adapters only for concrete dependency isolation or meaningful variation.
- **Compare feasible options:** include the current design/minimal extension and credible alternatives for consequential choices; include doing nothing when sufficient. Reject invariant violations first. If only one option is viable, explain why. Compare each option by driver → mechanism → consequence: correctness, change locality, coupling, resource cost, fault containment, security, operability, testability and reversibility. Identify worst plausible failure and detection. No arbitrary scores or pattern-driven design.
- **Resolve uncertainty:** distinguish evidence from estimates; use `a-deep-research` or a bounded spike for a material feasibility question (hypothesis, test, success criterion, stop condition). A toy POC does not establish production readiness.

## Express and challenge the chosen design

Show the before/after delta, responsibility/ownership, dependency direction and rationale. Cover affected views only: interfaces and semantic guarantees; data flow and persistence; state/concurrency/transactions; failures, retries and cleanup; trust/permissions; diagnostic signals; deployment, compatibility and rollback. For each important boundary identify caller, owner, valid inputs/outputs and relevant failure/lifecycle semantics. Trace critical success and failure paths end-to-end. For public changes identify consumers, compatibility window, migration order and rollback/data consequences; consider expand → migrate → contract where warranted.

Challenge lost capabilities, split invariants, hidden operational costs, undocumented consumer dependencies and abstractions with no real consumer. Identify a minimal independently verifiable slice and evidence that would falsify the design. See `references/decision-method.md` for a worked transport tradeoff and failure-path example, not a mandatory template.

## Decision authority and handoff

Apply `docs/06-AGENT-CONTRACT.md`: A local reversible decisions directly; B material recoverable decisions via Runtime `record_decision` (or `.vibe/progress.md` for durable project facts); C product semantics, public contracts, safety, data, cost or irreversible architecture require user approval. State context, options, rationale, tradeoffs, evidence/assumptions, rollback/revisit conditions and authority for material choices. A proposal is not approval. Persist a material approved decision in its existing authoritative home (spec/technical doc or Task decision); retain context, consequences and revisit conditions. Summarize/link project-level impact in progress, not a second decision ledger. Mark superseded current guidance and retain historical rationale.

Return the selected delta, drivers, alternatives, affected views, verification implications and open decisions at useful depth. Hand off to `a-engineering-spec` / `a-task-decompose` as needed. Design is complete when ownership, dependencies, key contracts and failure paths are clear, material uncertainty is resolved or explicitly blocks work, and no implementer must invent business behavior. Do not claim implementation acceptance. Local reversible decisions may need only a few sentences.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
