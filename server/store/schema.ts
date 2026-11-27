import { randomBytes } from "node:crypto";
import type { DatabaseSync } from "node:sqlite";
import { hashToken } from "../domain/secrets.ts";

export const CURRENT_SCHEMA_VERSION = 6;

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
  {
    version: 3,
    apply(db) {
      db.exec(`
        CREATE TABLE IF NOT EXISTS task (
          id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
          title TEXT NOT NULL, note TEXT, scope_json TEXT NOT NULL,
          status TEXT NOT NULL CHECK (status IN ('open','claimed','done','abandoned')),
          declared_by TEXT NOT NULL, claimed_by TEXT,
          created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, closed_reason TEXT,
          FOREIGN KEY (workspace_id, declared_by) REFERENCES membership(workspace_id, account_id),
          FOREIGN KEY (workspace_id, claimed_by) REFERENCES membership(workspace_id, account_id),
          CHECK ((status IN ('claimed','done') AND claimed_by IS NOT NULL) OR
                 (status IN ('open','abandoned') AND claimed_by IS NULL)),
          CHECK (status != 'abandoned' OR length(trim(closed_reason)) > 0 AND closed_reason IS NOT NULL)
        );
        CREATE INDEX IF NOT EXISTS task_workspace_status_idx ON task(workspace_id, status, updated_at);
        CREATE TABLE IF NOT EXISTS presence (
          workspace_id TEXT NOT NULL, account_id TEXT NOT NULL, last_seen_at INTEGER NOT NULL,
          PRIMARY KEY (workspace_id, account_id),
          FOREIGN KEY (workspace_id, account_id) REFERENCES membership(workspace_id, account_id) ON DELETE CASCADE
        );
      `);
    },
  },
  {
    version: 4,
    apply(db) {
      db.exec(`
        CREATE TABLE session_token_v4 (
          id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE, account_id TEXT NOT NULL REFERENCES account(id),
          name TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER,
          last_used_at INTEGER, revoked_at INTEGER,
          CHECK (expires_at IS NULL OR expires_at > created_at)
        );
        INSERT INTO session_token_v4 (id,token_hash,account_id,name,created_at,expires_at,revoked_at)
          SELECT 'tok_' || token_hash,token_hash,account_id,'Login token',created_at,expires_at,revoked_at FROM session_token;
        DROP TABLE session_token;
        ALTER TABLE session_token_v4 RENAME TO session_token;
        CREATE INDEX IF NOT EXISTS session_token_account_idx ON session_token(account_id, revoked_at);
      `);
    },
  },
  {
    // v5: single-user worklog sync. Drops the team model; keeps documents, versions, changes, idempotency.
    version: 5,
    apply(db) {
      db.exec(`
        ALTER TABLE workspace ADD COLUMN type TEXT NOT NULL DEFAULT 'engineering-dev';

        CREATE TABLE workspace_key (
          workspace_id TEXT PRIMARY KEY REFERENCES workspace(id) ON DELETE CASCADE,
          secret_hash TEXT NOT NULL UNIQUE,
          created_at INTEGER NOT NULL
        );
        INSERT INTO workspace_key (workspace_id, secret_hash, created_at)
          SELECT workspace_id, secret_hash, MAX(created_at) FROM task_key WHERE revoked_at IS NULL GROUP BY workspace_id;

        CREATE TABLE document_v5 (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
          path TEXT NOT NULL,
          version INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0),
          content_hash TEXT,
          updated_at TEXT NOT NULL,
          deleted_at TEXT,
          UNIQUE (workspace_id, path)
        );
        INSERT INTO document_v5 (id, workspace_id, path, version, content_hash, updated_at, deleted_at)
          SELECT id, workspace_id, path, version, content_hash, updated_at, deleted_at FROM document;

        CREATE TABLE document_version_v5 (
          document_id TEXT NOT NULL REFERENCES document_v5(id) ON DELETE CASCADE,
          version INTEGER NOT NULL CHECK (version >= 1),
          content TEXT,
          content_hash TEXT,
          created_at TEXT NOT NULL,
          PRIMARY KEY (document_id, version),
          CHECK ((content IS NULL AND content_hash IS NULL) OR (content IS NOT NULL AND content_hash IS NOT NULL))
        );
        INSERT INTO document_version_v5 (document_id, version, content, content_hash, created_at)
          SELECT document_id, version, content, content_hash, created_at FROM document_version;

        DROP TABLE document_version;
        DROP TABLE document;
        ALTER TABLE document_v5 RENAME TO document;
        ALTER TABLE document_version_v5 RENAME TO document_version;
        CREATE INDEX IF NOT EXISTS document_version_lookup_idx ON document_version (document_id, version);

        DROP TABLE IF EXISTS task;
        DROP TABLE IF EXISTS presence;
        DROP TABLE IF EXISTS workspace_token;
        DROP TABLE IF EXISTS session_token;
        DROP TABLE IF EXISTS invitation;
        DROP TABLE IF EXISTS membership;
        DROP TABLE IF EXISTS workspace_repo;
        DROP TABLE IF EXISTS task_key;
        DROP TABLE IF EXISTS account;
      `);
    },
  },
  {
    // v6: retain the current workspace Key so the admin API can return it.
    version: 6,
    apply(db) {
      db.exec("ALTER TABLE workspace_key ADD COLUMN secret TEXT");
      const rows = db.prepare("SELECT workspace_id FROM workspace_key WHERE secret IS NULL").all() as { workspace_id: string }[];
      const update = db.prepare("UPDATE workspace_key SET secret=?, secret_hash=? WHERE workspace_id=?");
      for (const row of rows) {
        const secret = randomBytes(24).toString("base64url");
        update.run(secret, hashToken(secret), row.workspace_id);
      }
      db.exec("CREATE UNIQUE INDEX workspace_key_secret_idx ON workspace_key(secret)");
    },
  },
];
