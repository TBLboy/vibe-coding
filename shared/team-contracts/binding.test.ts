import assert from "node:assert/strict";
import test from "node:test";
import { assertCanBind, validateBinding, type Binding } from "./binding.ts";

const VALID: Binding = {
  workspaceId: "ws_alpha1",
  serverUrl: "https://team.example.com",
  accountId: "acc_alice",
};

test("validateBinding accepts a complete binding", () => {
  assert.deepEqual(validateBinding({ ...VALID }), VALID);
});

test("validateBinding rejects missing or malformed fields", () => {
  assert.throws(() => validateBinding(null), /binding/);
  assert.throws(() => validateBinding({}), /workspaceId/);
  assert.throws(() => validateBinding({ ...VALID, workspaceId: "" }), /workspaceId/);
  assert.throws(() => validateBinding({ ...VALID, workspaceId: "ws/evil" }), /workspaceId/);
  assert.throws(() => validateBinding({ ...VALID, accountId: 42 }), /accountId/);
  assert.throws(() => validateBinding({ ...VALID, serverUrl: "ftp://example.com" }), /serverUrl/);
  assert.throws(() => validateBinding({ ...VALID, serverUrl: "example.com" }), /serverUrl/);
  assert.throws(() => validateBinding({ ...VALID, serverUrl: "https://example.com/?token=x" }), /serverUrl/);
  assert.throws(() => validateBinding({ ...VALID, serverUrl: "https://example.com/#frag" }), /serverUrl/);
});

test("assertCanBind allows first bind and same-workspace rebind", () => {
  assertCanBind(null, VALID);
  assertCanBind({ ...VALID }, { ...VALID });
});

test("assertCanBind refuses binding a directory to a second workspace", () => {
  const other: Binding = { ...VALID, workspaceId: "ws_beta2" };
  assert.throws(() => assertCanBind(VALID, other), /already bound/);
});
