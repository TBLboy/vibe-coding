---
name: a-business-clarify
description: Clarify vague business intent into atomic, testable business logic through active evidence gathering, one-question-at-a-time interviewing, controlled inference, and structured project-log updates.
license: MIT
compatibility: codex
metadata:
  stage: business-clarification
  output: atomic-business-logic
---

# Business Clarify

## Purpose

Turn incomplete, conversational, or contradictory product ideas into atomic business logic that can be implemented and verified without repeatedly guessing the user's intent.

This skill absorbs the useful part of `grill-me`: ask one high-value question at a time and provide a recommended answer. It is not an interrogation script. The user may answer, correct, or proactively add information at any moment.

## Inputs

Read, when available:

1. User statements in the current session.
2. `.project-log/requirements.md` and `.project-log/requirements/baseline.yaml`.
3. `.project-log/business-logic/atoms.yaml` and `open-questions.yaml`.
4. Existing code, tests, config, product documents, tickets, screenshots, and historical decisions.
5. `.project-log/docs/decision-authority.md`.

Never ask the user for information that can be reliably obtained from the project.

## Clarification Loop

### 1. Build the fact map

Classify every material statement as:

- **confirmed**: explicitly confirmed by the user or an active higher-priority source;
- **evidence-derived**: strongly supported by project artifacts;
- **inferred**: a reversible working assumption made by the Agent;
- **unknown**: required information not currently available;
- **conflict**: two sources prescribe incompatible behavior;
- **out-of-scope**: intentionally excluded from this increment.

Do not silently promote `inferred` to `confirmed`.

### 2. Clarify functional business logic

Record what the system should mean and do for users and the business:

- actors, roles, and permissions;
- normal scenarios and state transitions;
- inputs, outputs, side effects, and invariants;
- exception, boundary, concurrency, repeat-operation, and idempotency semantics;
- data ownership, visibility, and retention;
- scope, non-goals, and C-level product decisions.

Current code behavior is evidence, not automatic product authority.

### 3. Clarify technical business logic

Record how the current system actually carries the relevant business behavior:

- current implementation facts and state machines;
- interfaces, error codes, events, and data contracts;
- database, cache, queue, and external-system state relationships;
- transaction, consistency, concurrency, idempotency, and failure semantics;
- security, deployment, environment, and compatibility constraints;
- conflicts among code, config, tests, documentation, and active rules.

Technical business logic describes current facts and binding constraints. Do not select a future framework, library, lock, middleware, or refactoring strategy here; route those questions to `a-solution-research`.

### 4. Align functional and technical views

Compare what should happen with what currently happens. Classify each material result as:

- `confirmed-match`
- `missing-implementation`
- `implementation-drift`
- `missing-test`
- `test-drift`
- `constraint-conflict`
- `unknown`

Write the structured result to `.project-log/business-logic/clarification.yaml`.

### 5. Form atomic candidates

A business atom must describe one independently judgeable behavior, state transition, constraint, contract, flow step, or integration rule.

Split a statement when two parts can fail, change, or be accepted independently.

Each candidate should include:

- actor and trigger;
- preconditions and inputs;
- one core rule;
- outputs and side effects;
- exception/failure behavior;
- invariants;
- Given–When–Then acceptance criteria;
- source and authority.

### 6. Resolve autonomously where safe

Use the A/B/C authority matrix.

- A decisions: resolve directly.
- B decisions: resolve and create/update a decision-log entry.
- C decisions: ask the user.

Typical autonomous clarification decisions include naming, decomposing a compound rule, deriving an obvious error message category, or preserving existing behavior when the change does not target it.

### 7. Choose the next question

Only ask a question when the unresolved item materially blocks the current baseline.

Rank candidate questions by:

```text
question priority = business impact × uncertainty × future rework cost
```

Ask exactly one highest-priority question. Include:

- the question;
- why it matters;
- the recommended answer;
- the consequence of that recommendation;
- a fallback/default only when it is genuinely safe.

Do not ask a long questionnaire in one message.

### 8. Integrate user-provided information

When the user volunteers new information:

1. update the fact map;
2. revise or split affected atoms;
3. invalidate outdated assumptions;
4. identify downstream tasks/decisions that may need reopening;
5. then select the next highest-value unresolved question.

Do not mechanically return to an obsolete question sequence.

## Controlled Use of Solution Research

Load `a-solution-research` during clarification only when technology constrains the business decision, such as:

- feasibility is uncertain;
- latency, hardware, licensing, privacy, cost, or platform restrictions change the possible product behavior;
- two technical paths create materially different user experiences;
- the user asks whether a capability is possible before confirming the rule.

Do not research ordinary framework preferences during business clarification.

## Outputs

Update:

- `.project-log/business-logic/atoms.yaml`;
- `.project-log/business-logic/clarification.yaml`;
- `.project-log/business-logic/open-questions.yaml`;
- `.project-log/requirements.md` for a readable summary;
- `.project-log/tasks/task-list.yaml` for follow-up work;
- `.project-log/current-session.md`.

Draft or inferred atoms remain `draft` or `experimental`. Only promote to `active` when their authority and evidence satisfy the requirement baseline rules.

## Completion Gate

Business clarification is complete for the current scope when:

- the primary happy path is covered;
- high-impact branches, failure modes, permissions, and boundary cases are covered;
- every in-scope behavior is represented by atomic logic or explicitly marked unresolved;
- no unresolved C-level question blocks implementation;
- relevant technical business logic has been investigated;
- functional/technical conflicts are recorded and blocking conflicts are resolved or explicitly waiting on the user;
- future solution choices have been routed to research instead of being silently decided here;
- acceptance criteria are observable;
- remaining unknowns are low impact, intentionally deferred, or assigned to research tasks.

The goal is not to eliminate every conceivable unknown. It is to eliminate expensive hidden assumptions.
