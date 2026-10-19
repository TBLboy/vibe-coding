import assert from "node:assert/strict";
import test from "node:test";
import { shouldUpdateProgress, shouldWriteCurrentSession } from "../runtime/core/memory-policy.ts";

test("trivial completed work triggers no memory write", () => {
  assert.equal(shouldWriteCurrentSession({}), false);
  assert.equal(shouldUpdateProgress({}), false);
});

test("unfinished recoverable work or blocker updates current-session only", () => {
  assert.equal(shouldWriteCurrentSession({ unfinishedResumableWork: true }), true);
  assert.equal(shouldWriteCurrentSession({ blockerNeedsFollowUp: true }), true);
  assert.equal(shouldUpdateProgress({ unfinishedResumableWork: true }), false);
});

test("durable project facts update progress", () => {
  assert.equal(shouldUpdateProgress({ importantFeatureCompleted: true }), true);
  assert.equal(shouldUpdateProgress({ materialTechnicalDecision: true }), true);
  assert.equal(shouldUpdateProgress({ importantLimitationFound: true }), true);
});
