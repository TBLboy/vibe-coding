import assert from "node:assert/strict";
import test from "node:test";
import { activeTaskStorageKey, isActiveTaskPointer, isTaskPointer } from "../runtime/core/review-authorization.ts";
import { sessionMemoryRelativePath } from "../runtime/core/mode.ts";
test("Session recovery and active pointer keys are isolated", () => {
  assert.equal(sessionMemoryRelativePath("ses/123"), ".vibe/sessions/ses%2F123/current-session.md");
  assert.notEqual(sessionMemoryRelativePath("ses/123"), sessionMemoryRelativePath("ses_123"));
  assert.notEqual(activeTaskStorageKey("a"), activeTaskStorageKey("b"));
});
test("pointer must match the active Task", () => {
  const pointer = { taskID: "t", policy: "strict", active: true };
  assert.equal(isTaskPointer(pointer, "t"), true);
  assert.equal(isTaskPointer(pointer, "other"), false);
  assert.equal(isActiveTaskPointer({...pointer, active: false}), false);
  assert.equal(isTaskPointer({...pointer, policy: "invalid"}), false);
});
