import assert from "node:assert/strict";
import test from "node:test";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  DocumentConflictError,
  deleteDocument,
  getDocument,
  writeDocument,
} from "../server/domain/documents.ts";
import { getChanges } from "../server/domain/changes.ts";
import { applyMigrations, openTeamDatabase } from "../server/store/sqlite.ts";
import { CURRENT_SCHEMA_VERSION } from "../server/store/schema.ts";
import { hashContent } from "../runtime/core/team/manifest.ts";

function open() {
  const store = openTeamDatabase(":memory:");
  store.db.prepare("INSERT INTO org (id, name, created_at) VALUES (?, ?, ?)").run("org1", "Test", "2026-11-23T00:00:00.000Z");
  store.db.prepare("INSERT INTO workspace (id, org_id, name, slug, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)").run(
    "ws1",
    "org1",
    "Workspace",
    "workspace",
    "alice",
    "2026-11-23T00:00:00.000Z",
  );
  return store;
}

test("SQLite setup enables required pragmas and idempotent migrations", () => {
  const store = open();
  try {
    applyMigrations(store.db);
    const version = store.db.prepare("SELECT version FROM schema_meta WHERE id = 1").get() as { version: number };
    const foreignKeys = store.db.prepare("PRAGMA foreign_keys").get() as { foreign_keys: number };
    const busyTimeout = store.db.prepare("PRAGMA busy_timeout").get() as { timeout: number };
    assert.equal(version.version, CURRENT_SCHEMA_VERSION);
    assert.equal(foreignKeys.foreign_keys, 1);
    assert.equal(busyTimeout.timeout, 5000);
    assert.doesNotThrow(() => applyMigrations(store.db));
  } finally {
    store.close();
  }
});

test("document writes atomically version history, hashes and workspace sequence", () => {
  const store = open();
  try {
    const first = writeDocument(store, {
      workspaceId: "ws1",
      path: "specs/a.md",
      content: "first",
      accountId: "alice",
      expectedVersion: 0,
      now: "2026-11-23T10:00:00.000Z",
    });
    assert.deepEqual(first, { version: 1, hash: hashContent("first"), seq: 1 });

    const second = writeDocument(store, {
      workspaceId: "ws1",
      path: "specs/a.md",
      content: "second",
      accountId: "alice",
      expectedVersion: 1,
      now: "2026-11-23T10:01:00.000Z",
    });
    assert.deepEqual(second, { version: 2, hash: hashContent("second"), seq: 2 });

    const document = getDocument(store, { workspaceId: "ws1", path: "specs/a.md" });
    assert.equal(document?.version, 2);
    assert.equal(document?.content, "second");
    assert.equal(document?.ownerAccountId, "alice");
  } finally {
    store.close();
  }
});

test("If-Match conflicts expose only current version and hash and do not write", () => {
  const store = open();
  try {
    writeDocument(store, {
      workspaceId: "ws1",
      path: "specs/a.md",
      content: "server",
      accountId: "alice",
      expectedVersion: 0,
    });
    assert.throws(
      () =>
        writeDocument(store, {
          workspaceId: "ws1",
          path: "specs/a.md",
          content: "client",
          accountId: "bob",
          expectedVersion: 0,
        }),
      (error: unknown) => {
        assert.ok(error instanceof DocumentConflictError);
        assert.equal(error.currentVersion, 1);
        assert.equal(error.currentHash, hashContent("server"));
        assert.equal("content" in error, false);
        return true;
      },
    );
    assert.equal(getDocument(store, { workspaceId: "ws1", path: "specs/a.md" })?.content, "server");
  } finally {
    store.close();
  }
});

test("delete creates a tombstone and the change feed returns historical content", () => {
  const store = open();
  try {
    writeDocument(store, {
      workspaceId: "ws1",
      path: "members/alice/progress.md",
      content: "one",
      accountId: "alice",
      expectedVersion: 0,
    });
    writeDocument(store, {
      workspaceId: "ws1",
      path: "members/alice/progress.md",
      content: "two",
      accountId: "alice",
      expectedVersion: 1,
    });
    const deleted = deleteDocument(store, {
      workspaceId: "ws1",
      path: "members/alice/progress.md",
      accountId: "alice",
      expectedVersion: 2,
    });
    assert.deepEqual(deleted, { version: 3, hash: null, seq: 3 });
    assert.equal(getDocument(store, { workspaceId: "ws1", path: "members/alice/progress.md" })?.content, null);

    const feed = getChanges(store, { workspaceId: "ws1", since: 0 });
    assert.equal(feed.nextSeq, 3);
    assert.equal(feed.hasMore, false);
    assert.deepEqual(feed.changes.map((change) => change.content), ["one", "two", undefined]);
    assert.equal(feed.changes[2]?.op, "delete");
  } finally {
    store.close();
  }
});

test("change reads honor limit and byte bounds without skipping sequences", () => {
  const store = open();
  try {
    for (let i = 0; i < 3; i += 1) {
      writeDocument(store, {
        workspaceId: "ws1",
        path: `specs/${i}.md`,
        content: `content-${i}`,
        accountId: "alice",
        expectedVersion: 0,
      });
    }
    const limited = getChanges(store, { workspaceId: "ws1", since: 0, limit: 2 });
    assert.deepEqual(limited.changes.map((change) => change.seq), [1, 2]);
    assert.equal(limited.nextSeq, 2);
    assert.equal(limited.hasMore, true);

    const bounded = getChanges(store, { workspaceId: "ws1", since: 0, maxBytes: 260 });
    assert.ok(bounded.changes.length >= 1);
    assert.deepEqual(bounded.changes.map((change) => change.seq), [1]);
    assert.equal(bounded.hasMore, true);
    assert.equal(bounded.nextSeq, 1);
    assert.ok(Buffer.byteLength(JSON.stringify(bounded)) <= 260);
    assert.throws(() => getChanges(store, { workspaceId: "ws1", since: 0, maxBytes: 10 }), /too large/);
  } finally {
    store.close();
  }
});

test("late SQL failure rolls back document, history and sequence together", () => {
  const store = open();
  try {
    const input = { workspaceId: "ws1", path: "specs/a.md", accountId: "alice", content: "one", expectedVersion: 0 };
    writeDocument(store, input);
    store.db.exec(`CREATE TRIGGER reject_change BEFORE INSERT ON change
      BEGIN SELECT RAISE(ABORT, 'injected change failure'); END;`);
    assert.throws(() => writeDocument(store, { ...input, expectedVersion: 1, content: "two" }), /injected/);
    assert.equal(getDocument(store, input)?.content, "one");
    assert.equal(store.db.prepare("SELECT count(*) AS n FROM document_version").get()?.n, 1);
    assert.equal(store.db.prepare("SELECT seq FROM workspace_seq WHERE workspace_id = 'ws1'").get()?.seq, 1);
    store.db.exec("DROP TRIGGER reject_change");
    assert.equal(writeDocument(store, { ...input, expectedVersion: 1, content: "two" }).seq, 2);
  } finally { store.close(); }
});

test("feed detects internal and trailing holes and rejects cursors ahead of head", () => {
  const store = open();
  try {
    for (let i = 0; i < 3; i++) writeDocument(store, {
      workspaceId: "ws1", path: `specs/${i}.md`, content: "x", accountId: "alice", expectedVersion: 0,
    });
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
    store.db.exec(`INSERT INTO workspace (id, org_id, name, slug, created_by, created_at)
      VALUES ('ws2', 'org1', 'Two', 'two', 'bob', '2026-11-23')`);
    const input = { workspaceId: "ws1", path: "specs/a.md", content: "one", accountId: "alice", expectedVersion: 0 };
    writeDocument(store, input);
    const deletedAt = "2026-11-23T10:00:00.000Z";
    deleteDocument(store, { ...input, expectedVersion: 1, now: deletedAt });
    writeDocument(store, { ...input, content: "three", expectedVersion: 2 });
    assert.equal(getDocument(store, { ...input, version: 1 })?.content, "one");
    assert.equal(getDocument(store, { ...input, version: 2 })?.deletedAt, deletedAt);
    assert.equal(getDocument(store, { ...input, version: 999 }), null);
    assert.throws(() => getDocument(store, { ...input, version: 0 }), /version/);
    assert.equal(writeDocument(store, { ...input, workspaceId: "ws2" }).seq, 1);
    assert.deepEqual(getChanges(store, { workspaceId: "ws2", since: 0 }).changes.map(c => c.seq), [1]);
    assert.equal(getDocument(store, input)?.version, 3);
  } finally { store.close(); }
});

test("internal store supports index and validates content byte limits and invalid paths", () => {
  const store = open();
  try {
    const input = { workspaceId: "ws1", path: "index.json", content: "{}", accountId: "system", expectedVersion: 0 };
    assert.equal(writeDocument(store, input).version, 1);
    assert.throws(() => writeDocument(store, { ...input, path: "../escape" }), /path/);
    assert.throws(() => writeDocument(store, { ...input, path: "other/x" }), /layer/);
    const boundary = { ...input, path: "specs/large.md", content: "a".repeat(1024 * 1024) };
    assert.equal(writeDocument(store, boundary).version, 1);
    assert.throws(() => writeDocument(store, { ...boundary, content: boundary.content + "é" }), /too large/);
    assert.throws(() => writeDocument(store, { ...input, path: "specs/x.md", expectedVersion: -1 }), /expectedVersion/);
    assert.throws(() => deleteDocument(store, { ...input, path: "specs/missing.md" }), /not found/);
    assert.equal(getChanges(store, { workspaceId: "ws1", since: 0 }).changes.length, 2);
  } finally { store.close(); }
});

test("file database uses WAL and survives reopen; independent connections honor If-Match", () => {
  const dir = mkdtempSync(join(tmpdir(), "vibe-team-store-"));
  const path = join(dir, "team.db");
  const first = openTeamDatabase(path);
  let second: ReturnType<typeof openTeamDatabase> | undefined;
  try {
    first.db.exec(`INSERT INTO org VALUES ('org1', 'Test', '2026-11-23');
      INSERT INTO workspace (id, org_id, name, slug, created_by, created_at)
      VALUES ('ws1', 'org1', 'Test', 'test', 'alice', '2026-11-23')`);
    assert.equal(first.db.prepare("PRAGMA journal_mode").get()?.journal_mode, "wal");
    const input = { workspaceId: "ws1", path: "specs/a.md", content: "one", accountId: "alice", expectedVersion: 0 };
    writeDocument(first, input);
    second = openTeamDatabase(path);
    writeDocument(second, { ...input, expectedVersion: 1, content: "two" });
    assert.throws(() => writeDocument(first, { ...input, expectedVersion: 1, content: "stale" }), DocumentConflictError);
    first.close();
    assert.equal(getDocument(second, input)?.content, "two");
    second.close();
    second = openTeamDatabase(path);
    assert.deepEqual(getChanges(second, { workspaceId: "ws1", since: 0 }).changes.map(c => c.seq), [1, 2]);
    second.db.exec("UPDATE schema_meta SET version = 999");
    assert.throws(() => applyMigrations(second!.db), /unsupported schema version/);
    assert.equal(second.db.prepare("SELECT version FROM schema_meta").get()?.version, 999);
  } finally {
    first.close(); second?.close(); rmSync(dir, { recursive: true, force: true });
  }
});

test("empty and caught-up feeds do not move the cursor; query limits fail closed", () => {
  const store = open();
  try {
    assert.deepEqual(getChanges(store, { workspaceId: "ws1", since: 0 }), {
      changes: [], nextSeq: 0, hasMore: false,
    });
    const input = { workspaceId: "ws1", path: "specs/a.md", content: "\"\\\u0001中文", accountId: "alice", expectedVersion: 0 };
    writeDocument(store, input);
    assert.deepEqual(getChanges(store, { workspaceId: "ws1", since: 1 }), {
      changes: [], nextSeq: 1, hasMore: false,
    });
    const feed = getChanges(store, { workspaceId: "ws1", since: 0 });
    const size = Buffer.byteLength(JSON.stringify(feed));
    assert.deepEqual(getChanges(store, { workspaceId: "ws1", since: 0, maxBytes: size }), feed);
    assert.throws(() => getChanges(store, { workspaceId: "ws1", since: 0, maxBytes: size - 1 }), /too large/);
    for (const limit of [0, 501, 0.5, NaN]) {
      assert.throws(() => getChanges(store, { workspaceId: "ws1", since: 0, limit }), /limit/);
    }
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
    assert.throws(() => store.transaction(db => {
      db.exec("INSERT INTO org VALUES ('rolled-back', 'Test', '2026-11-23')");
      return Promise.resolve();
    }), /synchronous/);
    assert.equal(store.db.prepare("SELECT count(*) AS n FROM org WHERE id = 'rolled-back'").get()?.n, 0);
    assert.equal(store.transaction(() => 42), 42);
  } finally { store.close(); }
});

test("nested savepoints roll back only the failed inner mutation and preserve the outer boundary", () => {
  const store=open();
  try {
    store.transaction(db=>{
      db.exec("INSERT INTO org VALUES ('outer','Outer','now')");
      assert.throws(()=>store.transaction(inner=>{
        inner.exec("INSERT INTO org VALUES ('inner','Inner','now')"); throw new Error("injected inner failure");
      }),/injected inner failure/);
      assert.equal(db.prepare("SELECT count(*) AS n FROM org WHERE id='inner'").get()?.n,0);
    });
    assert.equal(store.db.prepare("SELECT count(*) AS n FROM org WHERE id='outer'").get()?.n,1);
    assert.throws(()=>store.transaction(()=>{
      store.transaction(db=>db.exec("INSERT INTO org VALUES ('joined','Joined','now')"));
      throw new Error("injected outer failure");
    }),/injected outer failure/);
    assert.equal(store.db.prepare("SELECT count(*) AS n FROM org WHERE id='joined'").get()?.n,0);
  } finally {store.close();}
});
