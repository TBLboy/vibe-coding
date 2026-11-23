import type { DatabaseSync } from "node:sqlite";

export const CURRENT_SCHEMA_VERSION = 2;

export interface Migration {
  version: number;
  apply(db: DatabaseSync): void;
}

export const MIGRATIONS: readonly Migration[] = [
  {
    version: 1,
    apply(db) {
      db.exec(`
        CREATE TABLE IF NOT EXISTS org (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS account (
          id TEXT PRIMARY KEY,
          org_id TEXT NOT NULL REFERENCES org(id),
          email TEXT NOT NULL,
          password_hash TEXT NOT NULL DEFAULT '',
          display_name TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          disabled_at TEXT,
          UNIQUE (org_id, email)
        );

        CREATE TABLE IF NOT EXISTS workspace (
          id TEXT PRIMARY KEY,
          org_id TEXT NOT NULL REFERENCES org(id),
          name TEXT NOT NULL,
          slug TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          archived_at TEXT,
          UNIQUE (org_id, slug)
        );

        CREATE TABLE IF NOT EXISTS schema_meta (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          version INTEGER NOT NULL CHECK (version >= 0)
        );

        CREATE TABLE IF NOT EXISTS workspace_seq (
          workspace_id TEXT PRIMARY KEY REFERENCES workspace(id) ON DELETE CASCADE,
          seq INTEGER NOT NULL DEFAULT 0 CHECK (seq >= 0)
        );

        CREATE TABLE IF NOT EXISTS document (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
          path TEXT NOT NULL,
          layer TEXT NOT NULL CHECK (layer IN ('constitution', 'specs', 'work', 'members', 'activity', 'index')),
          owner_account_id TEXT NOT NULL,
          version INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0),
          content_hash TEXT,
          updated_at TEXT NOT NULL,
          updated_by TEXT NOT NULL,
          deleted_at TEXT,
          UNIQUE (workspace_id, path)
        );

        CREATE TABLE IF NOT EXISTS document_version (
          document_id TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
          version INTEGER NOT NULL CHECK (version >= 1),
          content TEXT,
          content_hash TEXT,
          author TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY (document_id, version),
          CHECK ((content IS NULL AND content_hash IS NULL) OR (content IS NOT NULL AND content_hash IS NOT NULL))
        );

        CREATE TABLE IF NOT EXISTS change (
          workspace_id TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
          seq INTEGER NOT NULL CHECK (seq >= 1),
          path TEXT NOT NULL,
          op TEXT NOT NULL CHECK (op IN ('upsert', 'delete')),
          version INTEGER NOT NULL CHECK (version >= 1),
          created_at TEXT NOT NULL,
          PRIMARY KEY (workspace_id, seq)
        );

        CREATE INDEX IF NOT EXISTS change_workspace_path_idx
          ON change (workspace_id, path, seq);
        CREATE INDEX IF NOT EXISTS document_version_lookup_idx
          ON document_version (document_id, version);
      `);
    },
  },
  {
    version: 2,
    apply(db) {
      db.exec(`
        CREATE TABLE IF NOT EXISTS workspace_repo (
          id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
          url TEXT NOT NULL, branch TEXT NOT NULL, is_primary INTEGER NOT NULL CHECK (is_primary IN (0,1))
        );
        CREATE TABLE IF NOT EXISTS membership (
          workspace_id TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
          account_id TEXT NOT NULL REFERENCES account(id),
          role TEXT NOT NULL CHECK (role IN ('owner','member')),
          status TEXT NOT NULL CHECK (status IN ('invited','requested','active','removed')),
          invited_by TEXT REFERENCES account(id), created_at INTEGER NOT NULL, decided_at INTEGER,
          PRIMARY KEY (workspace_id, account_id)
        );
        CREATE TABLE IF NOT EXISTS invitation (
          id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
          org_id TEXT NOT NULL REFERENCES org(id), email TEXT NOT NULL,
          role TEXT NOT NULL CHECK (role = 'member'),
          status TEXT NOT NULL CHECK (status IN ('pending','accepted','revoked')),
          created_by TEXT NOT NULL REFERENCES account(id), created_at INTEGER NOT NULL, decided_at INTEGER,
          UNIQUE (workspace_id, email)
        );
        CREATE TABLE IF NOT EXISTS session_token (
          token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES account(id),
          created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, revoked_at INTEGER,
          CHECK (expires_at > created_at)
        );
        CREATE TABLE IF NOT EXISTS workspace_token (
          token_hash TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
          account_id TEXT NOT NULL REFERENCES account(id), created_at INTEGER NOT NULL,
          expires_at INTEGER NOT NULL, revoked_at INTEGER,
          FOREIGN KEY (workspace_id, account_id) REFERENCES membership(workspace_id, account_id),
          CHECK (expires_at > created_at)
        );
        CREATE TABLE IF NOT EXISTS task_key (
          id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
          secret_hash TEXT NOT NULL UNIQUE, created_at INTEGER NOT NULL, expires_at INTEGER, revoked_at INTEGER,
          CHECK (expires_at IS NULL OR expires_at > created_at)
        );
        CREATE TABLE IF NOT EXISTS idempotency (
          workspace_id TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
          key TEXT NOT NULL, request_hash TEXT NOT NULL, status INTEGER NOT NULL,
          response_json TEXT NOT NULL, created_at INTEGER NOT NULL,
          PRIMARY KEY (workspace_id, key)
        );
        CREATE INDEX IF NOT EXISTS membership_account_idx ON membership(account_id, status);
        CREATE INDEX IF NOT EXISTS workspace_token_member_idx ON workspace_token(workspace_id, account_id);
        CREATE INDEX IF NOT EXISTS idempotency_expiry_idx ON idempotency(created_at);
      `);
    },
  },
];
