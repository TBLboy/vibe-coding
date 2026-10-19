import assert from "node:assert/strict";
import test from "node:test";
import { buildModeCommandPrompt, isMode, isPendingModeChange, modeStorageKey, normalizeMode, pendingModeStorageKey, renderModeInstructions } from "../runtime/core/mode.ts";

test("only the three declared modes are valid", () => {
  assert.equal(isMode("fast"), true);
  assert.equal(isMode("balanced"), true);
  assert.equal(isMode("strict"), true);
  assert.equal(isMode("quick"), false);
  assert.equal(isMode("STRICT"), false);
});

test("missing or invalid stored mode defaults to balanced", () => {
  assert.equal(normalizeMode(undefined), "balanced");
  assert.equal(normalizeMode("old-mode"), "balanced");
  assert.equal(normalizeMode("strict"), "strict");
});

test("mode storage key is scoped by Session ID", () => {
  assert.notEqual(modeStorageKey("session-a"), modeStorageKey("session-b"));
  assert.notEqual(pendingModeStorageKey("session-a", "token"), pendingModeStorageKey("session-b", "token"));
  assert.throws(() => modeStorageKey("  "), /sessionID/);
  assert.throws(() => pendingModeStorageKey("session-a", " "), /token/);
});

test("bare mode command asks for acknowledgement only", () => {
  const prompt = buildModeCommandPrompt("fast", "  ", false, "token-123");
  assert.match(prompt, /invoked \/fast/);
  assert.match(prompt, /vibe_set_session_mode/);
  assert.match(prompt, /token-123/);
  assert.match(prompt, /do not start implementation/);
  assert.doesNotMatch(prompt, /After the tool succeeds, execute the following user request/);
});

test("mode command with attachments and no text treats attachments as task input", () => {
  const prompt = buildModeCommandPrompt("balanced", "", true, "token-123");
  assert.match(prompt, /attachments as the task input/);
  assert.doesNotMatch(prompt, /do not start implementation/);
});

test("mode command with task text preserves the task", () => {
  const prompt = buildModeCommandPrompt("strict", "  change the schema  ", false, "token-456");
  assert.match(prompt, /After the tool succeeds, execute the following user request/);
  assert.match(prompt, /change the schema/);
  assert.match(prompt, /frozen policy/);
});

test("only an unused matching pending token can authorize a mode change", () => {
  assert.equal(isPendingModeChange({ mode: "strict", token: "abc", consumed: false }, "strict", "abc"), true);
  assert.equal(isPendingModeChange({ mode: "strict", token: "abc", consumed: true }, "strict", "abc"), false);
  assert.equal(isPendingModeChange({ mode: "fast", token: "abc", consumed: false }, "strict", "abc"), false);
  assert.equal(isPendingModeChange(undefined, "strict", "abc"), false);
});

test("mode policy does not expose reviewer in fast or balanced", () => {
  assert.match(renderModeInstructions("fast"), /Do not invoke the reviewer/);
  assert.match(renderModeInstructions("balanced"), /Do not invoke the reviewer/);
  assert.match(renderModeInstructions("strict"), /reviewer returns go/);
});
