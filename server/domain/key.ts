import type { TeamDatabase } from "../store/sqlite.ts";
import { hashToken, issueSecret } from "./secrets.ts";

export const KEY_PATTERN = /^[A-Za-z0-9_-]{32}$/u;

/** Issue a fresh Key for a workspace, replacing any existing one. The hash authenticates; the secret supports admin retrieval. */
export function issueWorkspaceKey(store: TeamDatabase, workspaceId: string, now: number): string {
  const key = issueSecret(24);
  store.db.prepare(
    "INSERT INTO workspace_key (workspace_id, secret_hash, secret, created_at) VALUES (?, ?, ?, ?) " +
    "ON CONFLICT(workspace_id) DO UPDATE SET secret_hash = excluded.secret_hash, secret = excluded.secret, created_at = excluded.created_at",
  ).run(workspaceId, hashToken(key), key, now);
  return key;
}

export function getWorkspaceKey(store: TeamDatabase, workspaceId: string): string {
  const row = store.db.prepare("SELECT secret FROM workspace_key WHERE workspace_id=?").get(workspaceId) as { secret: string | null } | undefined;
  if (!row?.secret) throw new Error("workspace Key is unavailable");
  return row.secret;
}

/** Resolve a Key to its active (non-archived) workspace id, or undefined. */
export function findWorkspaceByKey(store: TeamDatabase, key: unknown): { workspaceId: string; archived: boolean } | undefined {
  if (typeof key !== "string" || !KEY_PATTERN.test(key)) return undefined;
  const row = store.db.prepare(
    "SELECT k.workspace_id AS id, w.archived_at AS archived FROM workspace_key k " +
    "JOIN workspace w ON w.id = k.workspace_id WHERE k.secret_hash = ?",
  ).get(hashToken(key)) as { id: string; archived: string | null } | undefined;
  return row ? { workspaceId: row.id, archived: row.archived !== null } : undefined;
}
