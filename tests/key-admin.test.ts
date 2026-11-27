import assert from "node:assert/strict";
import test from "node:test";
import { openTeamDatabase } from "../server/store/sqlite.ts";
import { findWorkspaceByKey, getWorkspaceKey, issueWorkspaceKey } from "../server/domain/key.ts";
import { isAdmin, readAdminToken } from "../server/domain/admin.ts";

function seed() {
  const store = openTeamDatabase(":memory:");
  store.db.prepare("INSERT INTO org (id, name, created_at) VALUES ('o', 'o', 't')").run();
  store.db.prepare("INSERT INTO workspace (id, org_id, name, slug, created_by, created_at) VALUES ('ws1','o','W','ws1','x','t')").run();
  return store;
}

test("key is 32 chars, stored with its hash, and rotates the single active key", () => {
  const store = seed();
  try {
    const key = issueWorkspaceKey(store, "ws1", 1);
    assert.match(key, /^[A-Za-z0-9_-]{32}$/);
    const rows = store.db.prepare("SELECT secret_hash, secret FROM workspace_key").all() as { secret_hash: string; secret: string }[];
    assert.equal(rows.length, 1);
    assert.notEqual(rows[0].secret_hash, key);
    assert.equal(rows[0].secret, key);
    assert.equal(getWorkspaceKey(store, "ws1"), key);
    assert.deepEqual(findWorkspaceByKey(store, key), { workspaceId: "ws1", archived: false });
    const next = issueWorkspaceKey(store, "ws1", 2);
    assert.equal(findWorkspaceByKey(store, key), undefined);
    assert.equal(findWorkspaceByKey(store, next)?.workspaceId, "ws1");
    assert.equal(findWorkspaceByKey(store, "short"), undefined);
    store.db.prepare("UPDATE workspace SET archived_at = 't' WHERE id = 'ws1'").run();
    assert.equal(findWorkspaceByKey(store, next)?.archived, true);
  } finally {
    store.close();
  }
});

test("admin token must be strong and compares in constant time", () => {
  assert.throws(() => readAdminToken({}), /WORKBENCH_ADMIN_TOKEN/);
  assert.throws(() => readAdminToken({ WORKBENCH_ADMIN_TOKEN: "short" }), /WORKBENCH_ADMIN_TOKEN/);
  const token = readAdminToken({ WORKBENCH_ADMIN_TOKEN: "x".repeat(32) });
  assert.equal(isAdmin(token, "x".repeat(32)), true);
  assert.equal(isAdmin(token, "y".repeat(32)), false);
  assert.equal(isAdmin(token, ""), false);
});
