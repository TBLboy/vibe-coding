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

Ordinary prose, quoted strings, code blocks, model output, and words such as “strict” never change mode. A mode command is a command, not a keyword heuristic.

## 3. Mode behavior

### Fast

`minimum necessary understanding → implement → targeted verification → deliver`

- No reviewer invocation, review record, or review gate.
- Task is optional; do not create one for trivial one-turn work.
- Create a Task only when durable tracking/recovery is useful: cross-session work, a blocker, multiple persistent deliverables, a material decision, high risk, or explicit acceptance criteria that must persist.
- Skip formal clarification/planning/breakdown when the request is clear and low risk.
- Verification remains required and proportional to risk.

### Balanced (default)

`understand normally → plan as needed → implement → verify → deliver`

- No reviewer invocation, review record, or review gate.
- Task is optional, not one-per-user-message. Create it for non-trivial multi-step or multi-file work, a durable deliverable, explicit acceptance criteria, a blocker, material risk/decision, or recovery needs.
- Business clarification, technical selection, and task breakdown are capabilities, not mandatory stages.
- Verification remains required and proportional to risk.

### Strict

`clarify → necessary technical decisions → task breakdown → implement → verify → independent review → deliver`

- A Task is mandatory.
- Before substantial implementation, make the business rules, scope, `doneWhen`, and material technical decisions explicit. Break down the work when it reduces risk or ambiguity.
- Reviewer invocation is mandatory after verification.
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
