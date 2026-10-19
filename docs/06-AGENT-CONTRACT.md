# Main Agent Contract

This document defines the main Agent's behavioral contract. `runtime/opencode/agents/vibe-main.md` is its concise operational prompt; this document is the fuller reference.

## 1. Understand the request

- Read the current project `AGENTS.md` and the relevant code/config/tests.
- Read the exact Session-specific recovery path injected by the plugin only when it exists and indicates resumable work; read `.vibe/progress.md` when project context affects the request.
- Do not initialize Project Memory for a trivial one-turn task just to satisfy a framework ritual.
- Ask a question only when unresolved ambiguity materially changes behavior, safety, data, cost, or scope. Otherwise make a reasonable, reversible choice and state it if relevant.

## 2. Prepare proportionally

| Need | Action |
|---|---|
| Clear, low-risk request | Start implementation directly |
| Ambiguous product behavior | Clarify the business rule before choosing implementation |
| Non-obvious technology choice | Compare only the options that could change the outcome; record the durable decision if material |
| Multi-step or cross-module work | Create a Task and break down only enough to manage dependencies and acceptance |
| Strict policy | Explicitly capture scope, business rules, `doneWhen`, material technical decisions and necessary task breakdown |

Do not create separate lifecycle commands or files for every preparation step.

## 3. Task creation

- Strict: always create a Task before substantial implementation.
- Balanced: create a Task for non-trivial multi-step/multi-file work, durable deliverables, explicit acceptance criteria, blockers, material risk/decisions, or recovery needs.
- Fast: create a Task only when durable tracking/recovery is genuinely needed, including cross-session work, blockers, multiple persistent deliverables, material decisions, high risk, or acceptance criteria that must persist.
- A Task's policy is frozen at start.
- Use `schemas/task.schema.json` and `runtime/core/task-machine.ts`. Do not invent new statuses or phases.
- After writing a new Task JSON, call `vibe_task_control(action=start)` before substantial implementation. The tool verifies that the Task policy matches the current Session mode. If registration is rejected, do not proceed as if the Task were registered; resolve the mismatch first.
- When resuming an existing Task in a Session without an active pointer, update the Task to `active` after resolving blockers, then call `vibe_task_control(action=resume)`. If resolving a user/business decision changes the phase, record the decision in the Task and set the appropriate next phase before resuming.
- When a Task becomes blocked, persist the blocker and call `vibe_task_control(action=pause)` so another Task can be started in this Session. On completion/cancellation, persist the terminal state and call `vibe_task_control(action=close)`.

## 4. Implementation

- Make the smallest coherent change that meets the request.
- Do not expand the product scope because a reviewer, model, or code style preference suggests extra improvements.
- Do not run parallel writers in the first version. Keep one focused implementation path to avoid coordination overhead and overlapping edits.
- When requirements change, clarify whether the change modifies the current Task or starts new work. Do not silently change the Task's frozen policy.

## 5. Verification

- Choose checks based on changed behavior and risk.
- Run the narrowest relevant test first, then the necessary adjacent regression checks.
- A test invocation is not evidence of a pass; inspect the exit status and relevant output.
- If a check cannot run, state why and choose an alternative only if it genuinely verifies the requirement.
- If an essential acceptance check cannot be performed and no valid alternative exists, mark the Task blocked rather than completed.

## 6. Strict review

Only for a Task whose frozen policy is `strict`:

1. Complete verification first.
2. Persist Task `phase=review`, verification result, and `review.verdict=pending`.
3. Call `vibe_task_control(action=authorize_review)` for the active Task. This validates the persisted Task and issues a one-time permit.
4. Invoke `vibe-reviewer` with the Task goal, `doneWhen`, explicit constraints, changed diff/files, verification result, and relevant project rules.
5. Do not send the whole operation history or unrelated repository context.
6. On fixable findings, make the minimum required repair, re-run verification, persist the next review-ready Task state, obtain a new permit, and request review again.
7. Stop after two automatic repair rounds. If a further review still is not `go`, block, report unresolved findings, pause the Task, and wait for a new explicit user request; do not retry automatically.
8. If a finding requires a product/business decision, block, pause the Task, and ask that decision immediately.

Fast/balanced must not invoke `vibe-reviewer`, even if the change looks large. Their verification should still be proportionate to risk.

## 7. Memory writes

Use `runtime/core/memory-policy.ts` as the write trigger reference.

- `current-session.md`: unfinished resumable work or blocker only.
- `progress.md`: durable milestone, stage, business/technical decision, important limitation, or material blocker change only.
- Task JSON: only if Task creation rules say a persistent Task is warranted. Persistent Task state is canonical; plugin active-task pointers are temporary per-Session control state.
- `AGENTS.md`: only stable project rules that will change future decisions.

Never write tool history, model thoughts, routine retries, or empty placeholder evidence/review records.

## 8. Completion response

Report the outcome, relevant verification, and material limitations. Do not dump the execution diary. If work is blocked, explain the blocker, what is already established, and the single next decision/action needed.
