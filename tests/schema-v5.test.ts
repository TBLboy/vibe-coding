import assert from "node:assert/strict";
import test from "node:test";
import { openTeamDatabase } from "../server/store/sqlite.ts";
import { CURRENT_SCHEMA_VERSION } from "../server/store/schema.ts";

test("schema v5 drops the team model and keeps document storage", () => {
  const store = openTeamDatabase(":memory:");
  try {
    assert.equal(CURRENT_SCHEMA_VERSION, 6);
    const tables = (store.db.prepare("SELECT name FROM sqlite_master WHERE type='table'").all() as { name: string }[]).map((r) => r.name);
    for (const t of ["workspace", "workspace_key", "document", "document_version", "change", "workspace_seq", "idempotency"]) {
      assert.ok(tables.includes(t), `missing ${t}`);
    }
    for (const t of ["account", "membership", "session_token", "workspace_token", "task_key", "task", "presence", "invitation", "workspace_repo"]) {
      assert.equal(tables.includes(t), false, `still present ${t}`);
    }
    const cols = (store.db.prepare("PRAGMA table_info(document)").all() as { name: string }[]).map((r) => r.name).sort();
    assert.deepEqual(cols, ["content_hash", "deleted_at", "id", "path", "updated_at", "version", "workspace_id"]);
    const wsCols = (store.db.prepare("PRAGMA table_info(workspace)").all() as { name: string }[]).map((r) => r.name);
    assert.ok(wsCols.includes("type"));
    const keyCols = (store.db.prepare("PRAGMA table_info(workspace_key)").all() as { name: string }[]).map((r) => r.name);
    assert.ok(keyCols.includes("secret"));
  } finally {
    store.close();
  }
});
