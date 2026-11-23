import { DatabaseSync, type DatabaseSyncOptions } from "node:sqlite";
import { isAsyncFunction } from "node:util/types";
import { randomUUID } from "node:crypto";
import { CURRENT_SCHEMA_VERSION, MIGRATIONS } from "./schema.ts";

export interface TeamDatabase {
  readonly db: DatabaseSync;
  transaction<T>(work: (db: DatabaseSync) => T): T;
  close(): void;
}

export function withTransaction<T>(db: DatabaseSync, work: (db: DatabaseSync) => T): T {
  if (isAsyncFunction(work)) throw new Error("SQLite transactions require a synchronous callback");
  const savepoint = db.isTransaction ? `vibe_${randomUUID().replaceAll("-", "")}` : null;
  db.exec(savepoint ? `SAVEPOINT ${savepoint}` : "BEGIN IMMEDIATE");
  try {
    const result = work(db);
    if (result !== null && (typeof result === "object" || typeof result === "function") &&
        typeof (result as { then?: unknown }).then === "function") {
      throw new Error("SQLite transactions require a synchronous callback");
    }
    db.exec(savepoint ? `RELEASE SAVEPOINT ${savepoint}` : "COMMIT");
    return result;
  } catch (error) {
    try {
      db.exec(savepoint ? `ROLLBACK TO SAVEPOINT ${savepoint}; RELEASE SAVEPOINT ${savepoint}` : "ROLLBACK");
    } catch {
      // Preserve the original failure; SQLite will already have rolled back on fatal errors.
    }
    throw error;
  }
}

export function applyMigrations(db: DatabaseSync): void {
  withTransaction(db, () => {
    db.exec(`
      CREATE TABLE IF NOT EXISTS schema_meta (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        version INTEGER NOT NULL CHECK (version >= 0)
      )
    `);
    db.prepare("INSERT OR IGNORE INTO schema_meta (id, version) VALUES (1, 0)").run();
    const row = db.prepare("SELECT version FROM schema_meta WHERE id = 1").get() as { version: number };
    if (!Number.isSafeInteger(row.version) || row.version < 0 || row.version > CURRENT_SCHEMA_VERSION) {
      throw new Error(`unsupported schema version: ${row.version}`);
    }
    let version = row.version;
    for (const migration of MIGRATIONS) {
      if (migration.version <= version) continue;
      migration.apply(db);
      db.prepare("UPDATE schema_meta SET version = ? WHERE id = 1").run(migration.version);
      version = migration.version;
    }
  });
}

export function openTeamDatabase(path: string, options?: DatabaseSyncOptions): TeamDatabase {
  const db = options === undefined ? new DatabaseSync(path) : new DatabaseSync(path, options);
  try {
    db.exec("PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 5000; PRAGMA foreign_keys = ON;");
    applyMigrations(db);
  } catch (error) {
    if (db.isOpen) db.close();
    throw error;
  }
  return {
    db,
    transaction<T>(work: (database: DatabaseSync) => T): T {
      return withTransaction(db, work);
    },
    close(): void {
      if (db.isOpen) db.close();
    },
  };
}
