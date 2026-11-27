import assert from "node:assert/strict";
import test from "node:test";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { DocumentConflictError, deleteDocument, getDocument, writeDocument } from "../server/domain/documents.ts";
import { getChanges } from "../server/domain/changes.ts";
import { applyMigrations, openTeamDatabase } from "../server/store/sqlite.ts";
import { CURRENT_SCHEMA_VERSION } from "../server/store/schema.ts";
import { hashContent } from "../shared/team-contracts/manifest.ts";

const T = "2026-11-27T00:00:00.000Z";
const A = ".vibe/docs/a.md";

function seed(db: { exec(sql: string): void }, id = "ws1") {
  db.exec(`INSERT OR IGNORE INTO org (id, name, created_at) VALUES ('single', 'single', '${T}');
    INSERT INTO workspace (id, org_id, name, slug, created_by, created_at, type) VALUES ('${id}', 'single', 'W', '${id}', 'admin', '${T}', 'engineering-dev')`);
}
function open() {
  const store = openTeamDatabase(":memory:");
  seed(store.db);
  return store;
}

test("SQLite setup enables required pragmas and idempotent migrations", () => {
  const store = open();
  try {
    applyMigrations(store.db);
    const version = store.db.prepare("SELECT version FROM schema_meta WHERE id = 1").get() as { version: number };
    assert.equal(version.version, CURRENT_SCHEMA_VERSION);
    assert.equal((store.db.prepare("PRAGMA foreign_keys").get() as { foreign_keys: number }).foreign_keys, 1);
    assert.equal((store.db.prepare("PRAGMA busy_timeout").get() as { timeout: number }).timeout, 5000);
    assert.doesNotThrow(() => applyMigrations(store.db));
  } finally { store.close(); }
});

test("document writes atomically version history, hashes and workspace sequence", () => {
  const store = open();
  try {
    assert.deepEqual(writeDocument(store, { workspaceId: "ws1", path: A, content: "first", expectedVersion: 0, now: T }), { version: 1, hash: hashContent("first"), seq: 1 });
    assert.deepEqual(writeDocument(store, { workspaceId: "ws1", path: A, content: "second", expectedVersion: 1, now: T }), { version: 2, hash: hashContent("second"), seq: 2 });
    const document = getDocument(store, { workspaceId: "ws1", path: A });
    assert.equal(document?.version, 2);
    assert.equal(document?.content, "second");
  } finally { store.close(); }
});

test("If-Match conflicts expose only current version and hash and do not write", () => {
  const store = open();
  try {
    writeDocument(store, { workspaceId: "ws1", path: A, content: "server", expectedVersion: 0 });
    assert.throws(() => writeDocument(store, { workspaceId: "ws1", path: A, content: "client", expectedVersion: 0 }), (error: unknown) => {
      assert.ok(error instanceof DocumentConflictError);
      assert.equal(error.currentVersion, 1);
      assert.equal(error.currentHash, hashContent("server"));
      assert.equal("content" in error, false);
      return true;
    });
    assert.equal(getDocument(store, { workspaceId: "ws1", path: A })?.content, "server");
  } finally { store.close(); }
});

test("delete creates a tombstone and the change feed returns historical content", () => {
  const store = open();
  try {
    const p = ".vibe/progress.md";
    writeDocument(store, { workspaceId: "ws1", path: p, content: "one", expectedVersion: 0 });
    writeDocument(store, { workspaceId: "ws1", path: p, content: "two", expectedVersion: 1 });
    assert.deepEqual(deleteDocument(store, { workspaceId: "ws1", path: p, expectedVersion: 2 }), { version: 3, hash: null, seq: 3 });
    assert.equal(getDocument(store, { workspaceId: "ws1", path: p })?.content, null);
    const feed = getChanges(store, { workspaceId: "ws1", since: 0 });
    assert.equal(feed.nextSeq, 3);
    assert.equal(feed.hasMore, false);
    assert.deepEqual(feed.changes.map((c) => c.content), ["one", "two", undefined]);
    assert.equal(feed.changes[2]?.op, "delete");
  } finally { store.close(); }
});

test("change reads honor limit and byte bounds without skipping sequences", () => {
  const store = open();
  try {
    for (let i = 0; i < 3; i += 1) writeDocument(store, { workspaceId: "ws1", path: `.vibe/docs/${i}.md`, content: `content-${i}`, expectedVersion: 0 });
    const limited = getChanges(store, { workspaceId: "ws1", since: 0, limit: 2 });
    assert.deepEqual(limited.changes.map((c) => c.seq), [1, 2]);
    assert.equal(limited.nextSeq, 2);
    assert.equal(limited.hasMore, true);
    const bounded = getChanges(store, { workspaceId: "ws1", since: 0, maxBytes: 270 });
    assert.deepEqual(bounded.changes.map((c) => c.seq), [1]);
    assert.equal(bounded.hasMore, true);
    assert.equal(bounded.nextSeq, 1);
    assert.ok(Buffer.byteLength(JSON.stringify(bounded)) <= 270);
    assert.throws(() => getChanges(store, { workspaceId: "ws1", since: 0, maxBytes: 10 }), /too large/);
  } finally { store.close(); }
});

test("late SQL failure rolls back document, history and sequence together", () => {
  const store = open();
  try {
    const input = { workspaceId: "ws1", path: A, content: "one", expectedVersion: 0 };
    writeDocument(store, input);
    store.db.exec(`CREATE TRIGGER reject_change BEFORE INSERT ON change BEGIN SELECT RAISE(ABORT, 'injected change failure'); END;`);
    assert.throws(() => writeDocument(store, { ...input, expectedVersion: 1, content: "two" }), /injected/);
    assert.equal(getDocument(store, input)?.content, "one");
    assert.equal((store.db.prepare("SELECT count(*) AS n FROM document_version").get() as { n: number }).n, 1);
    assert.equal((store.db.prepare("SELECT seq FROM workspace_seq WHERE workspace_id = 'ws1'").get() as { seq: number }).seq, 1);
    store.db.exec("DROP TRIGGER reject_change");
    assert.equal(writeDocument(store, { ...input, expectedVersion: 1, content: "two" }).seq, 2);
  } finally { store.close(); }
});

test("feed detects internal and trailing holes and rejects cursors ahead of head", () => {
  const store = open();
  try {
    for (let i = 0; i < 3; i++) writeDocument(store, { workspaceId: "ws1", path: `.vibe/docs/${i}.md`, content: "x", expectedVersion: 0 });
    assert.throws(() => getChanges(store, { workspaceId: "ws1", since: 4 }), /since|cursor/);
    store.db.exec("DELETE FROM change WHERE seq = 3");
    assert.throws(() => getChanges(store, { workspaceId: "ws1", since: 2 }), /gap|contiguous/);
    assert.throws(() => getChanges(store, { workspaceId: "ws1", since: 0 }), /gap|contiguous/);
    store.db.exec("DELETE FROM change WHERE seq = 1");
    assert.throws(() => getChanges(store, { workspaceId: "ws1", since: 0 }), /gap|contiguous/);
  } finally { store.close(); }
});

test("history preserves tombstone metadata after resurrection and isolates workspaces", () => {
  const store = open();
  try {
    seed(store.db, "ws2");
    const input = { workspaceId: "ws1", path: A, content: "one", expectedVersion: 0 };
    writeDocument(store, input);
    const deletedAt = "2026-11-27T10:00:00.000Z";
    deleteDocument(store, { ...input, expectedVersion: 1, now: deletedAt });
    writeDocument(store, { ...input, content: "three", expectedVersion: 2 });
    assert.equal(getDocument(store, { ...input, version: 1 })?.content, "one");
    assert.equal(getDocument(store, { ...input, version: 2 })?.deletedAt, deletedAt);
    assert.equal(getDocument(store, { ...input, version: 999 }), null);
    assert.throws(() => getDocument(store, { ...input, version: 0 }), /version/);
    assert.equal(writeDocument(store, { ...input, workspaceId: "ws2" }).seq, 1);
    assert.deepEqual(getChanges(store, { workspaceId: "ws2", since: 0 }).changes.map((c) => c.seq), [1]);
    assert.equal(getDocument(store, input)?.version, 3);
  } finally { store.close(); }
});

test("store accepts only AGENTS.md and .vibe/ paths, validates byte limits and missing deletes", () => {
  const store = open();
  try {
    const input = { workspaceId: "ws1", path: "AGENTS.md", content: "{}", expectedVersion: 0 };
    assert.equal(writeDocument(store, input).version, 1);
    for (const bad of ["../escape", "index.json", "specs/a.md", ".vibe/.sync/manifest.json"]) {
      assert.throws(() => writeDocument(store, { ...input, path: bad }), /path/, bad);
    }
    const boundary = { ...input, path: ".vibe/docs/large.md", content: "a".repeat(1024 * 1024) };
    assert.equal(writeDocument(store, boundary).version, 1);
    assert.throws(() => writeDocument(store, { ...boundary, content: boundary.content + "é" }), /too large/);
    assert.throws(() => writeDocument(store, { ...input, path: ".vibe/docs/x.md", expectedVersion: -1 }), /expectedVersion/);
    assert.throws(() => deleteDocument(store, { workspaceId: "ws1", path: ".vibe/docs/missing.md", expectedVersion: 0 }), /not found/);
    assert.equal(getChanges(store, { workspaceId: "ws1", since: 0 }).changes.length, 2);
  } finally { store.close(); }
});

test("file database uses WAL and survives reopen; independent connections honor If-Match", () => {
  const dir = mkdtempSync(join(tmpdir(), "vibe-wb-store-"));
  const path = join(dir, "team.db");
  const first = openTeamDatabase(path);
  let second: ReturnType<typeof openTeamDatabase> | undefined;
  try {
    seed(first.db);
    assert.equal((first.db.prepare("PRAGMA journal_mode").get() as { journal_mode: string }).journal_mode, "wal");
    const input = { workspaceId: "ws1", path: A, content: "one", expectedVersion: 0 };
    writeDocument(first, input);
    second = openTeamDatabase(path);
    writeDocument(second, { ...input, expectedVersion: 1, content: "two" });
    assert.throws(() => writeDocument(first, { ...input, expectedVersion: 1, content: "stale" }), DocumentConflictError);
    first.close();
    assert.equal(getDocument(second, input)?.content, "two");
    second.close();
    second = openTeamDatabase(path);
    assert.deepEqual(getChanges(second, { workspaceId: "ws1", since: 0 }).changes.map((c) => c.seq), [1, 2]);
    second.db.exec("UPDATE schema_meta SET version = 999");
    assert.throws(() => applyMigrations(second!.db), /unsupported schema version/);
  } finally { first.close(); second?.close(); rmSync(dir, { recursive: true, force: true }); }
});

test("empty and caught-up feeds do not move the cursor; query limits fail closed", () => {
  const store = open();
  try {
    assert.deepEqual(getChanges(store, { workspaceId: "ws1", since: 0 }), { changes: [], nextSeq: 0, hasMore: false });
    writeDocument(store, { workspaceId: "ws1", path: A, content: "\"\\\u0001中文", expectedVersion: 0 });
    assert.deepEqual(getChanges(store, { workspaceId: "ws1", since: 1 }), { changes: [], nextSeq: 1, hasMore: false });
    const feed = getChanges(store, { workspaceId: "ws1", since: 0 });
    const size = Buffer.byteLength(JSON.stringify(feed));
    assert.deepEqual(getChanges(store, { workspaceId: "ws1", since: 0, maxBytes: size }), feed);
    assert.throws(() => getChanges(store, { workspaceId: "ws1", since: 0, maxBytes: size - 1 }), /too large/);
    for (const limit of [0, 501, 0.5, NaN]) assert.throws(() => getChanges(store, { workspaceId: "ws1", since: 0, limit }), /limit/);
    assert.throws(() => getChanges(store, { workspaceId: "ws1", since: 0, maxBytes: 8 * 1024 * 1024 + 1 }), /maxBytes/);
    store.db.exec("DELETE FROM document_version");
    assert.throws(() => getChanges(store, { workspaceId: "ws1", since: 0 }), /missing upsert content/);
  } finally { store.close(); }
});

test("transaction boundary rejects async callbacks and rolls back returned promises", () => {
  const store = open();
  try {
    let invoked = false;
    assert.throws(() => store.transaction(async () => { invoked = true; }), /synchronous/);
    assert.equal(invoked, false);
    assert.throws(() => store.transaction((db) => { db.exec("INSERT INTO org VALUES ('rolled-back', 'Test', 'now')"); return Promise.resolve(); }), /synchronous/);
    assert.equal((store.db.prepare("SELECT count(*) AS n FROM org WHERE id = 'rolled-back'").get() as { n: number }).n, 0);
    assert.equal(store.transaction(() => 42), 42);
  } finally { store.close(); }
});

test("nested savepoints roll back only the failed inner mutation and preserve the outer boundary", () => {
  const store = open();
  try {
    store.transaction((db) => {
      db.exec("INSERT INTO org VALUES ('outer','Outer','now')");
      assert.throws(() => store.transaction((inner) => { inner.exec("INSERT INTO org VALUES ('inner','Inner','now')"); throw new Error("injected inner failure"); }), /injected inner failure/);
      assert.equal((db.prepare("SELECT count(*) AS n FROM org WHERE id='inner'").get() as { n: number }).n, 0);
    });
    assert.equal((store.db.prepare("SELECT count(*) AS n FROM org WHERE id='outer'").get() as { n: number }).n, 1);
    assert.throws(() => store.transaction(() => { store.transaction((db) => db.exec("INSERT INTO org VALUES ('joined','Joined','now')")); throw new Error("injected outer failure"); }), /injected outer failure/);
    assert.equal((store.db.prepare("SELECT count(*) AS n FROM org WHERE id='joined'").get() as { n: number }).n, 0);
  } finally { store.close(); }
});

test("R12: only the latest 20 versions per document are kept; current version is never pruned", () => {
  const store = open();
  try {
    for (let i = 0; i < 25; i++) writeDocument(store, { workspaceId: "ws1", path: A, content: `v${i + 1}`, expectedVersion: i });
    const n = (store.db.prepare("SELECT count(*) AS n FROM document_version").get() as { n: number }).n;
    assert.equal(n, 20);
    assert.equal(getDocument(store, { workspaceId: "ws1", path: A })?.content, "v25");
    assert.equal(getDocument(store, { workspaceId: "ws1", path: A, version: 5 }), null);
    assert.equal(getDocument(store, { workspaceId: "ws1", path: A, version: 6 })?.content, "v6");
  } finally { store.close(); }
});
