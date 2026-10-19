import assert from "node:assert/strict";
import test from "node:test";
import { shouldCreateTask } from "../runtime/core/task-policy.ts";

test("strict always creates a Task", () => {
  assert.equal(shouldCreateTask("strict", {}), true);
});

test("fast skips Task for trivial one-turn work", () => {
  assert.equal(shouldCreateTask("fast", {}), false);
});

test("fast creates Task when durable recovery or tracking is needed", () => {
  assert.equal(shouldCreateTask("fast", { crossSession: true }), true);
  assert.equal(shouldCreateTask("fast", { needsRecovery: true }), true);
  assert.equal(shouldCreateTask("fast", { blocked: true }), true);
  assert.equal(shouldCreateTask("fast", { highRisk: true }), true);
  assert.equal(shouldCreateTask("fast", { durableDecision: true }), true);
});

test("balanced creates Task for non-trivial multi-step or multi-file work", () => {
  assert.equal(shouldCreateTask("balanced", { multiStep: true }), true);
  assert.equal(shouldCreateTask("balanced", { multiFile: true }), true);
  assert.equal(shouldCreateTask("balanced", {}), false);
});

test("all modes persist explicit durable deliverables", () => {
  assert.equal(shouldCreateTask("fast", { durableDeliverable: true }), true);
  assert.equal(shouldCreateTask("balanced", { durableDeliverable: true }), true);
  assert.equal(shouldCreateTask("strict", { durableDeliverable: true }), true);
});
