---
name: a-business-code-align
description: "业务与代码对齐/一致性审计 | Audit and reconcile business logic, code implementation, configuration, and tests by building traceability, classifying mismatches, repairing only when authorized, and escalating semantic conflicts without letting code silently redefine requirements."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Business–Code–Test Alignment

## Mental model

An audit checks whether approved business semantics, production behavior and evidence agree. Neither current code nor a green suite can silently redefine business truth. An audit-only request authorizes investigation and findings, not repairs.

## Bidirectional traceability

Start with relevant project-level AGENTS.md rules and active baselines (use `.vibe/requirements/README.md`; cover all active rules for a whole-project audit), Task `doneWhen`, experimental rules clearly labeled, architecture constraints and recorded decisions. Inspect production paths, configuration, tests/fixtures, runtime evidence and known incidents.

- **Business → code/test:** trace each in-scope atom from trigger through real ingress, owner, branches, state/effects and errors to observable acceptance. Identify missing implementation, wiring, permissions, constraints, invariants or evidence. A test of a helper is not proof of production integration.
- **Code/test → business:** inventory externally visible behavior, persistent effects, permissions, defaults, limits, fallbacks and integrations. Trace each material behavior back to authority; classify internal-only behavior separately. Detect accidental new semantics and obsolete tests. Do not infer a new approved requirement from the code alone.
- **Evidence:** distinguish static match, observed behavior, test coverage and pending real-environment verification. Cite file/symbol/test/observed result; if evidence conflicts or is incomplete, record uncertainty rather than guessing. Use `a-verification` for new execution when needed.

## Findings and disposition

| Type | Meaning |
|---|---|
| `missing-implementation` | approved behavior absent/incomplete |
| `implementation-drift` | implementation diverges from approved rule |
| `missing-test` | behavior present; acceptance evidence missing |
| `test-drift` | test asserts semantics contrary to authority |
| `undocumented-behavior` | observable behavior lacks a rule; classify bug/internal/requirement candidate |
| `stale-business-logic` | evidence suggests recorded rule is obsolete; not approval to change it |
| `traceability-gap` | alignment possible, evidence/reference insufficient |
| `conflict` | authoritative sources disagree; cannot resolve independently |

Rank by business impact and evidence confidence, not file count. Separate findings from dispositions. A local reversible or B recoverable defect may be fixed **only when implementation is authorized**, risk/Policy permit it and scope is controlled; use `a-engineering-landing` and verify. Record B decisions via Runtime `record_decision` or durable progress. C semantics, public interfaces, safety, data, cost or irreversible changes require user approval; present one focused question, recommendation and impact. Supersede stale requirements only through baseline change control. Missing evidence is not automatic proof of a defect.

## Output and completion

For each finding give type, severity, confidence, affected rule, code/test/evidence, recommendation, authority, status and actual resolution. Small audits can use concise inline rows. Durable findings go to appropriate existing memory; authorized repairs use normal Task lifecycle and verification, blocking findings use `block` and recovery note as needed. Follow-up work stays a plan until Task policy warrants starting it. Never modify registered Task JSON or active baseline rules directly.

Audit complete means in-scope rules have implementation and evidence dispositions, material undocumented behavior is classified, conflicts/unknowns and owners of remaining work are explicit, and resolved findings have current evidence. Audit completion does not mean every finding is fixed or product acceptance achieved.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
