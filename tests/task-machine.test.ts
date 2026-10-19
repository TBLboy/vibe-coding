import assert from "node:assert/strict";
import test from "node:test";
import { createTask, transitionTask, type Task } from "../runtime/core/task-machine.ts";

function startVerification(task: Task): Task {
  const implementing = task.phase === "prepare"
    ? transitionTask(task, { type: "begin_implementation" })
    : task;
  return transitionTask(implementing, { type: "begin_verification" });
}

function passVerification(task: Task): Task {
  return transitionTask(task, {
    type: "verification_passed",
    summary: "Relevant checks passed.",
    checks: ["targeted test: passed"],
  });
}

test("Task IDs are path-safe and strict Tasks require acceptance criteria", () => {
  assert.throws(() => createTask({ id: "../escape", title: "Test", goal: "Test goal", doneWhen: [], policy: "balanced" }), /Task id must use/);
  assert.throws(() => createTask({ id: "t1", title: "Test", goal: "Test goal", doneWhen: [], policy: "strict" }), /doneWhen/);
});

test("balanced Task completes after verification without review", () => {
  const task = createTask({ id: "t1", title: "Test", goal: "Test goal", doneWhen: [], policy: "balanced" });
  const completed = passVerification(startVerification(task));
  assert.equal(completed.status, "completed");
  assert.equal(completed.phase, "complete");
  assert.equal(completed.review, undefined);
});

test("strict Task enters review after verification and cannot complete without go", () => {
  const task = createTask({ id: "t2", title: "Strict", goal: "Strict goal", doneWhen: ["criterion met"], policy: "strict" });
  const inReview = passVerification(startVerification(task));
  assert.equal(inReview.status, "active");
  assert.equal(inReview.phase, "review");
  assert.equal(inReview.review?.verdict, "pending");
  assert.throws(() => transitionTask(task, { type: "review_go" }), /strict Task in review/);
  const completed = transitionTask(inReview, { type: "review_go" });
  assert.equal(completed.status, "completed");
  assert.equal(completed.review?.verdict, "go");
});

test("verification failure returns to implementation", () => {
  const task = startVerification(createTask({ id: "t3", title: "Test", goal: "Test goal", doneWhen: [], policy: "balanced" }));
  const failed = transitionTask(task, { type: "verification_failed", summary: "Unit test failed", checks: ["unit test: failed"] });
  assert.equal(failed.status, "active");
  assert.equal(failed.phase, "implement");
  assert.equal(failed.verification.status, "failed");
});

test("strict review finding resets verification and permits at most two repair rounds", () => {
  let task = createTask({ id: "t4", title: "Strict", goal: "Strict goal", doneWhen: ["criterion met"], policy: "strict" });
  task = passVerification(startVerification(task));
  task = transitionTask(task, { type: "review_changes_required", verdict: "conditional", findings: [{ severity: "major", requirement: "criterion X", location: "src/x.ts:1", problem: "Criterion is not satisfied", requiredChange: "Implement criterion X" }] });
  assert.equal(task.phase, "implement");
  assert.equal(task.review?.repairRounds, 1);
  assert.equal(task.verification.status, "not_run");

  task = passVerification(startVerification(task));
  task = transitionTask(task, { type: "review_changes_required", verdict: "no-go", findings: [{ severity: "major", requirement: "criterion X", location: "src/x.ts:1", problem: "Criterion is still not satisfied", requiredChange: "Implement criterion X" }] });
  assert.equal(task.phase, "implement");
  assert.equal(task.review?.repairRounds, 2);

  task = passVerification(startVerification(task));
  task = transitionTask(task, { type: "review_changes_required", verdict: "conditional", findings: [{ severity: "major", requirement: "criterion X", location: "src/x.ts:1", problem: "The defect remains", requiredChange: "Fix the defect" }] });
  assert.equal(task.status, "blocked");
  assert.match(task.blocker ?? "", /after 2 automatic repair rounds/);
});

test("non-go review verdict requires at least one objective finding", () => {
  let task = createTask({ id: "t8", title: "Strict", goal: "Strict goal", doneWhen: ["criterion met"], policy: "strict" });
  task = passVerification(startVerification(task));
  assert.throws(() => transitionTask(task, {
    type: "review_changes_required",
    verdict: "conditional",
    findings: [],
  }), /at least one objective finding/);
});

test("review requiring user decision blocks immediately", () => {
  let task = createTask({ id: "t5", title: "Strict", goal: "Strict goal", doneWhen: ["criterion met"], policy: "strict" });
  task = passVerification(startVerification(task));
  task = transitionTask(task, {
    type: "review_changes_required",
    verdict: "no-go",
    findings: [{ severity: "critical", requirement: "Business rule must be defined", location: "login flow", problem: "Product behavior is ambiguous", requiredChange: "Ask the user to choose the intended behavior" }],
    requiresUserDecision: true,
  });
  assert.equal(task.status, "blocked");
  assert.match(task.blocker ?? "", /user decision/);
});

test("blocked Tasks resume at the same phase; terminal Tasks cannot be mutated", () => {
  let task = createTask({ id: "t6", title: "Test", goal: "Test goal", doneWhen: [], policy: "balanced" });
  task = transitionTask(task, { type: "block", reason: "Need credentials" });
  assert.equal(task.status, "blocked");
  assert.throws(() => transitionTask(task, { type: "begin_implementation" }), /resumed/);
  task = transitionTask(task, { type: "resume" });
  assert.equal(task.status, "active");
  task = passVerification(startVerification(task));
  assert.equal(task.status, "completed");
  assert.throws(() => transitionTask(task, { type: "cancel", reason: "late cancel" }), /terminal/);
});

test("a blocked strict review can resume into implementation only with a recorded decision", () => {
  let task = createTask({ id: "t9", title: "Strict", goal: "Strict goal", doneWhen: ["criterion met"], policy: "strict" });
  task = passVerification(startVerification(task));
  task = transitionTask(task, {
    type: "review_changes_required",
    verdict: "no-go",
    findings: [{ severity: "critical", requirement: "Business rule", location: "flow", problem: "Decision needed", requiredChange: "Clarify expected behavior" }],
    requiresUserDecision: true,
  });
  assert.equal(task.status, "blocked");
  assert.throws(() => transitionTask(task, { type: "resume", phase: "implement" }), /recorded decision/);
  const resumed = transitionTask(task, {
    type: "resume",
    phase: "implement",
    decision: "User confirmed the intended behavior.",
    nextAction: "Implement the confirmed behavior.",
  });
  assert.equal(resumed.status, "active");
  assert.equal(resumed.phase, "implement");
  assert.equal(resumed.verification.status, "not_run");
  assert.equal(resumed.decisions.at(-1), "User confirmed the intended behavior.");
});

test("not-applicable verification requires a reason", () => {
  const task = startVerification(createTask({ id: "t7", title: "Test", goal: "Test goal", doneWhen: [], policy: "balanced" }));
  assert.throws(() => transitionTask(task, {
    type: "verification_passed",
    status: "not_applicable",
    summary: "Not applicable",
    notApplicableReason: "   ",
  }), /not_applicable verification requires a reason/);
  const completed = transitionTask(task, {
    type: "verification_passed",
    status: "not_applicable",
    summary: "No executable behavior changed",
    notApplicableReason: "The change only updates a prose description.",
  });
  assert.equal(completed.verification.status, "not_applicable");
  assert.equal(completed.status, "completed");
});
