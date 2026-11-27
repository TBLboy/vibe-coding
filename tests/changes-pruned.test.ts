import assert from "node:assert/strict";
import test from "node:test";
import { openTeamDatabase } from "../server/store/sqlite.ts";
import { deleteDocument, writeDocument } from "../server/domain/documents.ts";
import { getChanges } from "../server/domain/changes.ts";

const T = "2026-11-27T00:00:00.000Z";
const P = ".vibe/docs/a.md";

function open() {
  const store = openTeamDatabase(":memory:");
  store.db.exec(`INSERT INTO org (id, name, created_at) VALUES ('single','single','${T}');
    INSERT INTO workspace (id, org_id, name, slug, created_by, created_at, type) VALUES ('ws1','single','W','ws1','admin','${T}','engineering-dev')`);
  return store;
}

test("a lagging cursor still reads a gapless feed after old versions were pruned", () => {
  const store = open();
  try {
    for (let i = 0; i < 25; i++) writeDocument(store, { workspaceId: "ws1", path: P, content: `v${i + 1}`, expectedVersion: i });
    const feed = getChanges(store, { workspaceId: "ws1", since: 0, limit: 500 });
    assert.equal(feed.changes.length, 25);
    assert.equal(feed.nextSeq, 25);
    assert.equal(feed.changes.at(-1)?.content, "v25");
    for (const c of feed.changes) assert.equal(c.op, "upsert");
  } finally { store.close(); }
});

test("pruned upserts of a document that is now deleted surface as deletes", () => {
  const store = open();
  try {
    for (let i = 0; i < 25; i++) writeDocument(store, { workspaceId: "ws1", path: P, content: `v${i + 1}`, expectedVersion: i });
    deleteDocument(store, { workspaceId: "ws1", path: P, expectedVersion: 25 });
    const feed = getChanges(store, { workspaceId: "ws1", since: 0, limit: 500 });
    assert.equal(feed.changes.length, 26);
    assert.equal(feed.changes.at(-1)?.op, "delete");
  } finally { store.close(); }
});
