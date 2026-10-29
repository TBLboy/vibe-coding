import assert from "node:assert/strict";
import test from "node:test";
import { activeTaskStorageKey, canAuthorizeReview, canCloseTask, isActiveTaskPointer, isReviewPermit, isTaskPointer, reviewPermitStorageKey, isReviewCompletion, reviewCompletionStorageKey } from "../runtime/core/review-authorization.ts";
import { createTask, transitionTask } from "../runtime/core/task-machine.ts";
import { sessionMemoryRelativePath } from "../runtime/core/mode.ts";

function reviewReadyStrictTask() {
  let task = createTask({ id: "task-strict-1", title: "Strict", goal: "Strict goal", doneWhen: ["criterion met"], policy: "strict" });
  task = transitionTask(task, { type: "begin_implementation" });
  task = transitionTask(task, { type: "begin_verification" });
  task = transitionTask(task, { type: "verification_passed", summary: "Checks passed", checks: ["unit: passed"] });
  return task;
}

test("Session recovery path is scoped to an encoded Session ID", () => {
  assert.equal(sessionMemoryRelativePath("ses_123"), ".vibe/sessions/ses_123/current-session.md");
  assert.equal(sessionMemoryRelativePath("ses/123"), ".vibe/sessions/ses%2F123/current-session.md");
  assert.notEqual(sessionMemoryRelativePath("ses_123"), sessionMemoryRelativePath("ses_456"));
  assert.notEqual(sessionMemoryRelativePath("ses/123"), sessionMemoryRelativePath("ses_123"));
});

test("active task and review permit keys are Session-scoped", () => {
  assert.notEqual(activeTaskStorageKey("ses_a"), activeTaskStorageKey("ses_b"));
  assert.notEqual(reviewPermitStorageKey("ses_a"), reviewPermitStorageKey("ses_b"));
});

test("review authorization requires the current Task to be strict, active, verified and in review", () => {
  const ready = reviewReadyStrictTask();
  assert.equal(canAuthorizeReview(ready, ready.id), true);
  assert.equal(canAuthorizeReview(ready, "another-task"), false);
  assert.equal(canAuthorizeReview({ ...ready, policy: "balanced" }, ready.id), false);
  assert.equal(canAuthorizeReview({ ...ready, phase: "implement" }, ready.id), false);
  assert.equal(canAuthorizeReview({ ...ready, verification: { status: "failed", summary: "x", checks: [], limitations: [] } }, ready.id), false);
  assert.equal(canAuthorizeReview({ ...ready, review: { ...ready.review!, verdict: "conditional" } }, ready.id), false);
});

test("only a matching active pointer and unused permit are accepted", () => {
  assert.equal(isTaskPointer({ taskID: "task-1", policy: "strict", active: true }, "task-1"), true);
  assert.equal(isActiveTaskPointer({ taskID: "task-1", policy: "strict", active: true }, "task-1"), true);
  assert.equal(isTaskPointer({ taskID: "task-1", policy: "strict", active: false }), true);
  assert.equal(isActiveTaskPointer({ taskID: "task-1", policy: "strict", active: false }), false);
  assert.equal(isReviewPermit({ taskID: "task-1", consumed: false }, "task-1"), true);
  assert.equal(isReviewPermit({ taskID: "task-1", consumed: true }), false);
  assert.equal(isReviewPermit({ taskID: "task-1", consumed: false }, "task-2"), false);
});

test("a Task can close only when terminal verification and strict review requirements are satisfied", () => {
  const balanced = createTask({ id: "task-balanced", title: "Balanced", goal: "Goal", doneWhen: [], policy: "balanced" });
  const blockedBalanced = transitionTask(balanced, { type: "block", reason: "Need decision" });
  assert.equal(canCloseTask(blockedBalanced, balanced.id), false);
  const cancelled = transitionTask(blockedBalanced, { type: "cancel", reason: "Cancelled by user" });
  assert.equal(canCloseTask(cancelled, balanced.id), true);

  const readyStrict = reviewReadyStrictTask();
  assert.equal(canCloseTask(readyStrict, readyStrict.id), false);
  const completedStrict = transitionTask(readyStrict, { type: "review_go" });
  assert.equal(canCloseTask(completedStrict, readyStrict.id), true);
});

test("a strict Task cannot close unless the reviewer was actually invoked", () => {
  const strictDone = {
    id: "s", title: "t", goal: "g", doneWhen: ["x"], policy: "strict", status: "completed", phase: "complete", decisions: [],
    verification: { status: "passed", summary: "ok", checks: ["npm test"], limitations: [] },
    review: { verdict: "go", findings: [], repairRounds: 0 },
  };
  assert.equal(canCloseTask(strictDone, "s", true), true);
  assert.equal(canCloseTask(strictDone, "s", false), false);
  const balancedDone = { ...strictDone, policy: "balanced", review: undefined };
  assert.equal(canCloseTask(balancedDone, "s", false), true);
  assert.equal(isReviewCompletion({ taskID: "s" }, "s"), true);
  assert.equal(isReviewCompletion({ taskID: "other" }, "s"), false);
  assert.match(reviewCompletionStorageKey("ses_1"), /review-completed:ses_1$/);
});
