# Product Contract

Status: baseline approved for implementation.

## 1. Goal

Make the amount of process proportional to the work. Preserve engineering judgment, project continuity, verification and strict review when explicitly requested; remove mandatory ceremony.

## 2. Session mode

A Session has one mode:

- `fast`
- `balanced`
- `strict`

A new Session defaults to `balanced`. The mode remains active for that OpenCode Session until the user explicitly changes it. The plugin stores it by OpenCode `sessionID`; it is not stored in project progress files. Mode commands are queued, so they do not interrupt the currently running action.

Only the native slash commands `/fast`, `/balanced`, and `/strict` change the mode. Each may be used alone or with trailing task text:

- `/fast` — switch mode and briefly confirm; do not start a task.
- `/strict change the database schema` — switch mode, confirm briefly, and execute the supplied request in the same turn.

Ordinary prose, quoted strings, code blocks, model output, and words such as “strict” never change mode. A mode command is a command, not a keyword heuristic. On successful change, briefly confirm the mode; when the registered Task pointer has a different frozen policy, report that policy, its active or paused/closed pointer state, and that the new mode governs new work. Do not resume or modify an existing Task merely because mode changed.

## 3. Mode behavior

All modes use the same Agent, Skills and Project Memory. Mode selects engineering process and quality gates, not intelligence or permissions to skip correctness. Ordinary consultation, explanation and read-only investigation without a durable deliverable or tracking need do not create a Task or invoke a reviewer in any mode. This includes preliminary investigation for a possible future change; implementation or an agreed durable engineering deliverable is different. Do not recast actual implementation as consultation to bypass strict review. A registered Task always follows its own frozen policy.

### Fast

`minimum necessary understanding → implement → targeted verification → deliver`

- No reviewer invocation, review record, or review gate.
- Task is optional; do not create one for trivial one-turn work.
- Create a Task only when durable tracking/recovery is useful: cross-session work, a blocker, one or more durable deliverables, a material decision/risk, or explicit acceptance criteria that must persist.
- Take the shortest correct path even across multiple files. Skip unnecessary formal clarification/planning/breakdown; use relevant Skills and sufficient evidence when useful.
- Verification remains required and proportional to risk.

### Balanced (default)

`understand normally → plan as needed → implement → verify → deliver`

- No reviewer invocation, review record, or review gate.
- Task is optional, not one-per-user-message. Create it for non-trivial coordination across steps/files/modules, a durable deliverable, persistent acceptance criteria, a blocker, material risk/decision, or recovery needs. File count alone is not a persistence signal; simple work can be as light as Fast.
- Business clarification, technical selection, and task breakdown are capabilities, not mandatory stages.
- Verification remains required and proportional to risk.

### Strict

`prepare as needed → execute agreed work → verify → independent review → deliver`

- A Task is mandatory for engineering implementation (including small edits) and engineering work needing durable tracking (including agreed deliverables), not ordinary consultation as defined above.
- Before executing that tracked work, make the business rules, scope, `doneWhen`, and material technical decisions explicit. Break down the work when it reduces risk or ambiguity.
- Reviewer invocation is mandatory after verification of a strict Task. No prescribed sequence of Skills or separate design/report files; use only what supports the agreed outcome.
- A Task cannot complete until the reviewer returns `go`.
- Reviewer `conditional` or fixable `no-go` findings cause a bounded repair cycle: fix only required findings → re-verify → re-review.
- Maximum: two automatic repair rounds after the initial review. If a third review still requires changes, block, report the unresolved findings, and stop automatic retries. Any further attempt requires a new explicit user request. If a product/business decision is required, block immediately and ask the user.

There is no independent reviewer toggle. Mode is the only user-facing control for review depth.

## 4. One lifecycle, conditional depth

The framework has one lifecycle, not three separate workflow implementations:

1. **Prepare** — understand the request; clarify business rules, select technology, or decompose tasks only when useful/required by policy.
2. **Implement** — make the smallest coherent change.
3. **Verify** — run checks appropriate to the change and risk.
4. **Review** — strict only.
5. **Complete** — deliver the result and persist durable facts only when needed.

A stage name is not a requirement to create a separate command, Agent, file, or state object.

## 5. Verification

Mode and risk are distinct. Assess the actual consequences, affected contracts/consumers, data and security, uncertainty and rollback. `quick` is local/reversible with targeted checks; `standard` changes normal behavior and requires adjacent regression/integration as relevant; `strict` covers consequential contract/data/migration/security/permission/concurrency changes, critical failure or difficult recovery. File count, duration and code volume alone do not determine risk. Fast and Balanced may execute quick or standard work with the appropriate evidence; neither may implement strict-risk work. Stop, explain the concrete risk and request explicit `/strict`; pause/cancel old work as appropriate and start a new strict Task. Runtime enforces declared risk, not arbitrary shell edits. Strict Tasks require review even for quick work.

Verification is required for code changes. Automated tests are not mandatory when they are not applicable; an alternative targeted check and a reason must be recorded in the result. Examples:

- prose/docs: inspect the final text and links;
- a simple style change: inspect the diff and relevant build/UI path;
- business logic: run targeted unit/integration tests;
- schema/migration: validate the migration and affected integration behavior.

Do not claim a test passed if it was not run. If a required check cannot run because of an environment limitation, disclose the limitation. A Task remains blocked if the missing check is essential to the acceptance criteria and no valid alternative exists.

## 6. Scope discipline

Do not add features because they might be useful later. Do not turn review suggestions into requirements. A change is in scope only if it satisfies the current request, an agreed acceptance criterion, or a necessary correctness/safety constraint.

## 7. Delivery

The final response must state:

- what changed;
- what verification ran and its result;
- material limitations or checks not run.

Keep it concise. Do not include a tool-by-tool diary.

## Personal Workbench refinement

This is a small personal framework. Workbench creation + local Key binding is the primary initialization route. Explicit local initialization is supported using the same published engineering-dev template; Workbench may instead create a workspace from existing valid engineering logs without template overlay. Sync remains AGENTS.md and .vibe/ except device-private data; Git stays independent. No team accounts, sync dashboard, dedicated conflict management, new Runtime objects or product metrics.
