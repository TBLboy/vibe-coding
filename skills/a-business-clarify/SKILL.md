---
name: a-business-clarify
description: "Clarify vague business intent into atomic, testable business logic through active evidence gathering, one-question-at-a-time interviewing, controlled inference, and durable V2 memory updates."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Business Clarify

## Purpose

Turn incomplete, conversational, or contradictory product ideas into atomic business logic that can be implemented and verified without repeatedly guessing the user's intent.

Ask one high-value question at a time and provide a recommended answer. This is not an interrogation script. The user may answer, correct, or proactively add information at any moment.

## Inputs

Read, when available:

1. User statements in the current Session.
2. The project's durable memory: `AGENTS.md`, `.vibe/progress.md`, `.vibe/requirements.md` (if present), the active Task JSON, and the current Session's `current-session.md`.
3. Existing code, tests, config, product documents, tickets, screenshots, and historical decisions.

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

Technical business logic describes current facts and binding constraints. Do not select a future framework, library, lock, middleware, or refactoring strategy here; route those questions to `a-deep-research`.

### 4. Align functional and technical views

Compare what should happen with what currently happens. Classify each material result as:

- `confirmed-match`
- `missing-implementation`
- `implementation-drift`
- `missing-test`
- `test-drift`
- `constraint-conflict`
- `unknown`

Keep confirmed atoms and open questions in the working clarification list. When clarification changes the active Task's scope, update the Task `goal`/`doneWhen` and, if work is unfinished, the current Session's `current-session.md`.

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

## Decision authority

- **A**: reversible, local, low-impact — resolve directly.
- **B**: material but recoverable — resolve, then record it in the active Task JSON `decisions` (or `.vibe/progress.md` when it is a durable project fact).
- **C**: product semantics, safety, data, public interfaces, cost, or irreversible architecture — ask the user; one question, with a recommendation and its consequence.

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

## Controlled Use of Research

Load `a-deep-research` during clarification only when technology constrains the business decision, such as:

- feasibility is uncertain;
- latency, hardware, licensing, privacy, cost, or platform restrictions change the possible product behavior;
- two technical paths create materially different user experiences;
- the user asks whether a capability is possible before confirming the rule.

Do not research ordinary framework preferences during business clarification.

## Outputs

- Confirmed atoms with acceptance criteria: into the active Task `doneWhen` for this increment; into `.vibe/requirements.md` only when they are durable business rules worth a baseline (`a-requirement-baseline`).
- Material B-level decisions: Task JSON `decisions`.
- Open C-level questions that block work: Task `blocker` and the current Session's `current-session.md`.
- Follow-up work: new Task JSON files only when persistent tracking is warranted.

Draft or inferred atoms stay labeled as such. Promote to confirmed only when their authority and evidence satisfy the baseline rules.

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
- remaining unknowns are low impact, intentionally deferred, or assigned to research.

The goal is not to eliminate every conceivable unknown. It is to eliminate expensive hidden assumptions.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
