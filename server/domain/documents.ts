import { Buffer } from "node:buffer";
import { randomUUID } from "node:crypto";
import { DatabaseSync } from "node:sqlite";
import { hashContent } from "../../shared/team-contracts/manifest.ts";
import { validateServerPath } from "../../shared/team-contracts/layout.ts";
import { validateWorkspacePath } from "./paths.ts";
import { withTransaction, type TeamDatabase } from "../store/sqlite.ts";

const MAX_DOCUMENT_BYTES = 1024 * 1024;
const MAX_KEPT_VERSIONS = 20;

export interface WriteDocumentInput {
  workspaceId: string;
  path: string;
  content: string | null;
  expectedVersion: number;
  now?: string;
}

export interface DocumentWriteResult {
  version: number;
  hash: string | null;
  seq: number;
}

export interface DocumentRecord {
  id: string;
  workspaceId: string;
  path: string;
  version: number;
  hash: string | null;
  content: string | null;
  updatedAt: string;
  deletedAt: string | null;
}

export interface DocumentLookup {
  workspaceId: string;
  path: string;
  version?: number;
}

export class DocumentConflictError extends Error {
  readonly code = "conflict";
  readonly currentVersion: number;
  readonly currentHash: string | null;

  constructor(currentVersion: number, currentHash: string | null) {
    super("document version conflict");
    this.name = "DocumentConflictError";
    this.currentVersion = currentVersion;
    this.currentHash = currentHash;
  }
}

type DbLike = TeamDatabase | DatabaseSync;

function databaseOf(value: DbLike): DatabaseSync {
  return value instanceof DatabaseSync ? value : value.db;
}

function transact<T>(value: DbLike, work: (db: DatabaseSync) => T): T {
  return value instanceof DatabaseSync ? withTransaction(value, work) : value.transaction(work);
}

function assertInput(input: WriteDocumentInput): void {
  if (!validateWorkspacePath(input.path).ok) throw new Error("invalid document path");
  if (typeof input.workspaceId !== "string" || input.workspaceId.length === 0) {
    throw new Error("invalid workspaceId");
  }
  if (!Number.isSafeInteger(input.expectedVersion) || input.expectedVersion < 0) {
    throw new Error("invalid expectedVersion");
  }
  if (input.content !== null && typeof input.content !== "string") {
    throw new Error("invalid document content");
  }
  if (input.content !== null && Buffer.byteLength(input.content, "utf8") > MAX_DOCUMENT_BYTES) {
    throw new Error("document content is too large");
  }
}

interface StoredDocumentRow {
  id: string;
  workspace_id: string;
  path: string;
  version: number;
  content_hash: string | null;
  content: string | null;
  updated_at: string;
  deleted_at: string | null;
}

function readStoredDocument(db: DatabaseSync, lookup: DocumentLookup): StoredDocumentRow | undefined {
  if (!validateServerPath(lookup.path).ok) throw new Error("invalid document path");
  if (lookup.version !== undefined && (!Number.isSafeInteger(lookup.version) || lookup.version < 1)) {
    throw new Error("invalid document version");
  }
  const row = db.prepare(`
    SELECT d.id, d.workspace_id, d.path,
           d.version, d.content_hash, v.content, d.updated_at, d.deleted_at
      FROM document AS d
      LEFT JOIN document_version AS v
        ON v.document_id = d.id AND v.version = d.version
     WHERE d.workspace_id = ? AND d.path = ?
  `).get(lookup.workspaceId, lookup.path) as StoredDocumentRow | undefined;
  if (!row || lookup.version === undefined || lookup.version === row.version) return row;
  return db.prepare(`
    SELECT d.id, d.workspace_id, d.path,
           v.version, v.content_hash, v.content, v.created_at AS updated_at,
           CASE WHEN v.content IS NULL THEN v.created_at ELSE NULL END AS deleted_at
      FROM document AS d
      JOIN document_version AS v ON v.document_id = d.id
     WHERE d.workspace_id = ? AND d.path = ? AND v.version = ?
  `).get(lookup.workspaceId, lookup.path, lookup.version) as StoredDocumentRow | undefined;
}

function mapDocument(row: StoredDocumentRow | undefined): DocumentRecord | null {
  if (!row) return null;
  return {
    id: row.id,
    workspaceId: row.workspace_id,
    path: row.path,
    version: row.version,
    hash: row.content_hash,
    content: row.content,
    updatedAt: row.updated_at,
    deletedAt: row.deleted_at,
  };
}

export function getDocument(value: DbLike, lookup: DocumentLookup): DocumentRecord | null {
  return mapDocument(readStoredDocument(databaseOf(value), lookup));
}

export function getDocumentVersion(
  value: DbLike,
  lookup: Required<DocumentLookup>,
): DocumentRecord | null {
  return mapDocument(readStoredDocument(databaseOf(value), lookup));
}

export function writeDocument(value: DbLike, input: WriteDocumentInput): DocumentWriteResult {
  assertInput(input);
  const now = input.now ?? new Date().toISOString();
  const contentHash = input.content === null ? null : hashContent(input.content);

  return transact(value, (db) => {
    const existing = db.prepare(
      "SELECT id, version, content_hash FROM document WHERE workspace_id = ? AND path = ?",
    ).get(input.workspaceId, input.path) as {
      id: string;
      version: number;
      content_hash: string | null;
    } | undefined;
    const currentVersion = existing?.version ?? 0;
    const currentHash = existing?.content_hash ?? null;
    if (currentVersion !== input.expectedVersion) {
      throw new DocumentConflictError(currentVersion, currentHash);
    }
    if (!existing && input.content === null) throw new Error("document not found");

    const version = currentVersion + 1;
    if (!Number.isSafeInteger(version)) throw new Error("document version exhausted");
    const documentId = existing?.id ?? randomUUID();
    if (!existing) {
      db.prepare(`
        INSERT INTO document
          (id, workspace_id, path, version, content_hash, updated_at, deleted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
      `).run(
        documentId,
        input.workspaceId,
        input.path,
        version,
        contentHash,
        now,
        input.content === null ? now : null,
      );
    } else {
      db.prepare(`
        UPDATE document
           SET version = ?, content_hash = ?, updated_at = ?, deleted_at = ?
         WHERE id = ?
      `).run(version, contentHash, now, input.content === null ? now : null, documentId);
    }
    db.prepare(`
      INSERT INTO document_version
        (document_id, version, content, content_hash, created_at)
      VALUES (?, ?, ?, ?, ?)
    `).run(documentId, version, input.content, contentHash, now);
    // R12: keep the latest 20 versions as a safety net; tombstones (content IS NULL) are permanent.
    db.prepare("DELETE FROM document_version WHERE document_id = ? AND content IS NOT NULL AND version <= ?").run(documentId, version - MAX_KEPT_VERSIONS);

    db.prepare("INSERT OR IGNORE INTO workspace_seq (workspace_id, seq) VALUES (?, 0)").run(input.workspaceId);
    db.prepare("UPDATE workspace_seq SET seq = seq + 1 WHERE workspace_id = ?").run(input.workspaceId);
    const sequence = db.prepare("SELECT seq FROM workspace_seq WHERE workspace_id = ?").get(input.workspaceId) as {
      seq: number;
    };
    if (!Number.isSafeInteger(sequence.seq)) throw new Error("workspace sequence exhausted");
    db.prepare(`
      INSERT INTO change (workspace_id, seq, path, op, version, created_at)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(input.workspaceId, sequence.seq, input.path, input.content === null ? "delete" : "upsert", version, now);

    return { version, hash: contentHash, seq: sequence.seq };
  });
}

export function deleteDocument(
  value: DbLike,
  input: Omit<WriteDocumentInput, "content">,
): DocumentWriteResult {
  return writeDocument(value, { ...input, content: null });
}
