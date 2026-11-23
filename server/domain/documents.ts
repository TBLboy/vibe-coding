import { Buffer } from "node:buffer";
import { randomUUID } from "node:crypto";
import { DatabaseSync } from "node:sqlite";
import { hashContent } from "../../runtime/core/team/manifest.ts";
import { layerOf, validateServerPath, type Layer } from "../../runtime/core/team/layout.ts";
import { withTransaction, type TeamDatabase } from "../store/sqlite.ts";

const MAX_DOCUMENT_BYTES = 1024 * 1024;

export interface WriteDocumentInput {
  workspaceId: string;
  path: string;
  content: string | null;
  accountId: string;
  expectedVersion: number;
  ownerAccountId?: string;
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
  layer: Layer;
  ownerAccountId: string;
  version: number;
  hash: string | null;
  content: string | null;
  updatedAt: string;
  updatedBy: string;
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

function assertInput(input: WriteDocumentInput): Layer {
  if (!validateServerPath(input.path).ok) throw new Error("invalid document path");
  const layer = layerOf(input.path);
  if (layer === undefined) throw new Error("invalid document layer");
  if (typeof input.workspaceId !== "string" || input.workspaceId.length === 0) {
    throw new Error("invalid workspaceId");
  }
  if (typeof input.accountId !== "string" || input.accountId.length === 0) {
    throw new Error("invalid accountId");
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
  return layer;
}

interface StoredDocumentRow {
  id: string;
  workspace_id: string;
  path: string;
  layer: string;
  owner_account_id: string;
  version: number;
  content_hash: string | null;
  content: string | null;
  updated_at: string;
  updated_by: string;
  deleted_at: string | null;
}

function readStoredDocument(db: DatabaseSync, lookup: DocumentLookup): StoredDocumentRow | undefined {
  if (!validateServerPath(lookup.path).ok) throw new Error("invalid document path");
  if (lookup.version !== undefined && (!Number.isSafeInteger(lookup.version) || lookup.version < 1)) {
    throw new Error("invalid document version");
  }
  const row = db.prepare(`
    SELECT d.id, d.workspace_id, d.path, d.layer, d.owner_account_id,
           d.version, d.content_hash, v.content, d.updated_at, d.updated_by, d.deleted_at
      FROM document AS d
      LEFT JOIN document_version AS v
        ON v.document_id = d.id AND v.version = d.version
     WHERE d.workspace_id = ? AND d.path = ?
  `).get(lookup.workspaceId, lookup.path) as StoredDocumentRow | undefined;
  if (!row || lookup.version === undefined || lookup.version === row.version) return row;
  return db.prepare(`
    SELECT d.id, d.workspace_id, d.path, d.layer, d.owner_account_id,
           v.version, v.content_hash, v.content, v.created_at AS updated_at,
           v.author AS updated_by,
           CASE WHEN v.content IS NULL THEN v.created_at ELSE NULL END AS deleted_at
      FROM document AS d
      JOIN document_version AS v ON v.document_id = d.id
     WHERE d.workspace_id = ? AND d.path = ? AND v.version = ?
  `).get(lookup.workspaceId, lookup.path, lookup.version) as StoredDocumentRow | undefined;
}

function mapDocument(row: StoredDocumentRow | undefined): DocumentRecord | null {
  if (!row) return null;
  if (!["constitution", "specs", "work", "members", "activity", "index"].includes(row.layer)) {
    throw new Error("database contains invalid document layer");
  }
  return {
    id: row.id,
    workspaceId: row.workspace_id,
    path: row.path,
    layer: row.layer as Layer,
    ownerAccountId: row.owner_account_id,
    version: row.version,
    hash: row.content_hash,
    content: row.content,
    updatedAt: row.updated_at,
    updatedBy: row.updated_by,
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
  const layer = assertInput(input);
  const now = input.now ?? new Date().toISOString();
  const contentHash = input.content === null ? null : hashContent(input.content);

  return transact(value, (db) => {
    const existing = db.prepare(
      "SELECT id, version, content_hash, owner_account_id FROM document WHERE workspace_id = ? AND path = ?",
    ).get(input.workspaceId, input.path) as {
      id: string;
      version: number;
      content_hash: string | null;
      owner_account_id: string;
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
    const ownerAccountId = existing?.owner_account_id ?? input.ownerAccountId ?? input.accountId;
    if (!existing) {
      db.prepare(`
        INSERT INTO document
          (id, workspace_id, path, layer, owner_account_id, version, content_hash, updated_at, updated_by, deleted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `).run(
        documentId,
        input.workspaceId,
        input.path,
        layer,
        ownerAccountId,
        version,
        contentHash,
        now,
        input.accountId,
        input.content === null ? now : null,
      );
    } else {
      db.prepare(`
        UPDATE document
           SET version = ?, content_hash = ?, updated_at = ?, updated_by = ?, deleted_at = ?
         WHERE id = ?
      `).run(version, contentHash, now, input.accountId, input.content === null ? now : null, documentId);
    }
    db.prepare(`
      INSERT INTO document_version
        (document_id, version, content, content_hash, author, created_at)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(documentId, version, input.content, contentHash, input.accountId, now);

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
