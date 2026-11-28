---
name: a-codebase-onboarding
description: "接手代码库/摸清架构/代码入门 | Onboard an existing codebase by mapping architecture, current observable behavior, tests, data, integrations, and risks without treating code behavior as automatically authoritative business logic."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Codebase Onboarding

## Mental model and scope

Build an evidence map of how the system currently works so another engineer can reason about it. Start with the user's intended work, not a directory inventory. `b-project-structure-survey` answers where things live; onboarding connects real entry points to behavior, state, integrations and risks. `b-source-code-tutoring` teaches a selected source path. No automatic handoff or code repair.

## Investigate the system

- Establish the actual package/workspace roots, stack, build/configuration, deployment assumptions, entry points, tests and external dependencies. Find which profiles, flags, registrations and defaults select the live implementation; distinguish available code from enabled code.
- Trace a few representative use cases from trigger through authorization/validation, domain decisions, state owners and persistence, external calls, result and failure handling. Include material alternate paths (retry, cancellation, duplicate request, recovery) when relevant. Identify the boundaries between observed code, mocks, generated wiring and external systems. Do not equate an import graph with runtime execution.
- Reconcile data models, lifecycle transitions, invariants, configuration and actual consumers. Check how existing tests exercise the entry points and what they omit. Execute safe, isolated checks only when authorized and useful; do not start external services, write production data or modify product code as part of onboarding.
- Compare relevant `AGENTS.md`, indexed active requirements and durable progress/decisions against implementation. Use progress as navigation, selectively follow relevant technical docs and lessons, and check their scope/revision before relying on them. Report stale guidance and correct only authorized current knowledge; do not rewrite approved rules from observed behavior. Distinguish normative rules from observations: explicit user-approved contract, actual execution evidence, test assertions, static code/configuration, comments and inference. A test or current code is not automatically business authority; record conflicts, do not silently choose a winner.
- Derive candidate business atoms from material behaviors, with source, trigger, condition, effect and exception. Label them `evidence-derived`, `inferred` or `unknown`; keep any proposed baseline `draft` until authorized. Use `a-business-code-align` when a full bidirectional audit is requested, and `a-business-clarify` for unresolved semantics.

## Deliver a usable map

Provide system boundaries and key paths with source anchors; observed behavior and candidate business rules; known constraints, risks, contradictory evidence and important gaps; and the smallest useful next investigation or authorized work. Scale coverage to the goal; do not claim whole-system knowledge from a sampled path or successful build. Distinguish static understanding, executed checks and unverified external behavior.

Default to a concise report. Persist a useful onboarding document under `.vibe/docs/` when warranted, and only durable project facts in `.vibe/progress.md`. Propose stable project-level rules for `AGENTS.md` and require user approval before editing it. Use the existing requirement baseline and lesson rules for those knowledge types; do not auto-activate inferred business rules. A follow-up list is a plan, not registered Task state. Do not create placeholder Tasks for findings.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
