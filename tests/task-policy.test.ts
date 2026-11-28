import assert from "node:assert/strict";
import test from "node:test";
import { shouldCreateTask } from "../runtime/core/task-policy.ts";

test("strict engineering work creates a Task even without complexity signals", () => {
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

test("ordinary consultation is light in every mode, durable work still persists", () => {
  for (const mode of ["fast", "balanced", "strict"] as const) {
    assert.equal(shouldCreateTask(mode, { consultationOnly: true }), false);
    assert.equal(shouldCreateTask(mode, { consultationOnly: true, multiStep: true, multiFile: true }), false);
    assert.equal(shouldCreateTask(mode, { durableDeliverable: true }), true);
    // Durable tracking signals take precedence over a contradictory consultation hint.
    assert.equal(shouldCreateTask(mode, { consultationOnly: true, needsRecovery: true }), true);
  }
});

test("clear multi-file work is light in fast; meaningful coordination is tracked in balanced", () => {
  assert.equal(shouldCreateTask("fast", { multiFile: true, multiStep: true }), false);
  assert.equal(shouldCreateTask("balanced", { multiFile: true }), true);
  assert.equal(shouldCreateTask("balanced", {}), false);
  assert.equal(shouldCreateTask("strict", {}), true);
});
