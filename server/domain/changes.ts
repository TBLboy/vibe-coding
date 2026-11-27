import { Buffer } from "node:buffer";
import { DatabaseSync } from "node:sqlite";
import { validateChanges, type Change } from "../../shared/team-contracts/change-feed.ts";
import { type TeamDatabase } from "../store/sqlite.ts";

export interface ChangeWithContent extends Change {
  content?: string;
  createdAt: string;
}

export interface ChangeQuery {
  workspaceId: string;
  since: number;
  limit?: number;
  maxBytes?: number;
}

export interface ChangeBatch {
  changes: ChangeWithContent[];
  nextSeq: number;
  hasMore: boolean;
}

type DbLike = TeamDatabase | DatabaseSync;

function databaseOf(value: DbLike): DatabaseSync {
  return value instanceof DatabaseSync ? value : value.db;
}

export function getChanges(value: DbLike, query: ChangeQuery): ChangeBatch {
  if (typeof query.workspaceId !== "string" || query.workspaceId.length === 0) {
    throw new Error("invalid workspaceId");
  }
  if (!Number.isSafeInteger(query.since) || query.since < 0) throw new Error("invalid since");
  const limit = query.limit ?? 200;
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 500) throw new Error("invalid limit");
  const maxBytes = query.maxBytes ?? 8 * 1024 * 1024;
  if (!Number.isSafeInteger(maxBytes) || maxBytes < 1 || maxBytes > 8 * 1024 * 1024) {
    throw new Error("invalid maxBytes");
  }

  const rows = databaseOf(value).prepare(`
    SELECT s.seq AS head, c.seq, c.path, c.op, c.version, c.created_at,
           v.content, v.content_hash,
           d.version AS cur_version, d.content_hash AS cur_hash, d.deleted_at AS cur_deleted, cv.content AS cur_content
      FROM workspace_seq AS s
      LEFT JOIN change AS c ON c.workspace_id = s.workspace_id AND c.seq > ?
      LEFT JOIN document AS d
        ON d.workspace_id = c.workspace_id AND d.path = c.path
      LEFT JOIN document_version AS v
        ON v.document_id = d.id AND v.version = c.version
      LEFT JOIN document_version AS cv
        ON cv.document_id = d.id AND cv.version = d.version
     WHERE s.workspace_id = ?
     ORDER BY c.seq ASC
     LIMIT ?
  `).all(query.since, query.workspaceId, limit + 1) as Array<{
    head: number;
    seq: number | null;
    path: string;
    op: "upsert" | "delete";
    version: number;
    created_at: string;
    content: string | null;
    content_hash: string | null;
    cur_version: number | null;
    cur_hash: string | null;
    cur_deleted: string | null;
    cur_content: string | null;
  }>;

  // The head and rows come from one SQLite statement/snapshot. An absent tail
  // must not be mistaken for a fully caught-up client.
  const head = rows[0]?.head ?? 0;
  if (query.since > head) throw new Error("invalid since: cursor is ahead of workspace head");
  const available: ChangeWithContent[] = [];
  for (const row of rows) {
    if (row.seq === null) continue;
    const change: ChangeWithContent = {
      seq: row.seq,
      path: row.path,
      op: row.op,
      version: row.version,
      createdAt: row.created_at,
    };
    if (row.op === "upsert") {
      if (row.content !== null && row.content_hash !== null) {
        change.hash = row.content_hash;
        change.content = row.content;
      } else if (row.cur_deleted !== null) {
        // R12: this version was pruned and the document is deleted now; surface it as a delete.
        change.op = "delete";
      } else if (row.cur_content !== null && row.cur_hash !== null && row.cur_version !== null) {
        // R12: pruned version of a live document; coalesce into the current state.
        change.version = row.cur_version;
        change.hash = row.cur_hash;
        change.content = row.cur_content;
      } else throw new Error("change-feed: missing upsert content");
    }
    available.push(change);
  }
  validateChanges(query.since, available);
  const lastAvailable = available.at(-1)?.seq ?? query.since;
  if (available.length < limit + 1 && lastAvailable !== head) {
    throw new Error("change-feed: trailing sequence gap");
  }
  const batch: ChangeBatch = { changes: [], nextSeq: query.since, hasMore: head > query.since };
  for (const change of available.slice(0, limit)) {
    const candidate: ChangeBatch = {
      changes: [...batch.changes, change], nextSeq: change.seq, hasMore: change.seq < head,
    };
    if (Buffer.byteLength(JSON.stringify(candidate), "utf8") > maxBytes) {
      if (batch.changes.length === 0) throw new Error("change-feed: response too large");
      break;
    }
    Object.assign(batch, candidate);
  }
  if (Buffer.byteLength(JSON.stringify(batch), "utf8") > maxBytes) {
    throw new Error("change-feed: response too large");
  }
  return batch;
}
