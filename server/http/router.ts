import { createServer, type IncomingMessage, type Server } from "node:http";
import { createServer as createSecureServer, type Server as SecureServer } from "node:https";
import { readFileSync } from "node:fs";
import type { TeamDatabase } from "../store/sqlite.ts";
import { CURRENT_SCHEMA_VERSION } from "../store/schema.ts";
import { assertId } from "../../shared/team-contracts/binding.ts";
import { validateWorkspacePath } from "../domain/paths.ts";
import { isAdmin } from "../domain/admin.ts";
import { findWorkspaceByKey, getWorkspaceKey } from "../domain/key.ts";
import { archiveWorkspace, createWorkspace, getWorkspace, listWorkspaces, renameWorkspace } from "../domain/workspace.ts";
import { DocumentConflictError, writeDocument, deleteDocument, getDocument } from "../domain/documents.ts";
import { getChanges } from "../domain/changes.ts";
import { ApiError, bodyObject, forbidden, invalid, notFound, unauthenticated } from "./errors.ts";
import { idempotentMutation, type Reply } from "./idempotency.ts";

export interface RequestLog { event: "api_request"; method: string; route: string; status: number; durationMs: number }
export interface ServerOptions { adminToken: string; now?: () => number; logger?: (entry: RequestLog) => void; tls?: { cert: string; key: string } }
const MAX_BODY = 2 * 1024 * 1024;

function readBody(req: IncomingMessage): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    let bytes = 0, failed = false; const chunks: Buffer[] = [];
    req.on("data", (chunk: Buffer) => {
      if (failed) return;
      bytes += chunk.length;
      if (bytes > MAX_BODY) { failed = true; chunks.length = 0; reject(new ApiError(413, "too_large", "Request body is too large")); return; }
      chunks.push(chunk);
    });
    req.on("end", () => {
      if (failed) return;
      try {
        if (bytes === 0) { resolve({}); return; }
        if (!/^application\/json(?:\s*;|$)/iu.test(req.headers["content-type"] ?? "")) throw new ApiError(400, "invalid_request", "Expected application/json");
        resolve(bodyObject(JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks)))));
      } catch (error) { reject(error instanceof ApiError ? error : new ApiError(400, "invalid_request", "Invalid JSON body")); }
    });
    req.on("error", () => reject(new ApiError(400, "invalid_request", "Request stream failed")));
    req.on("aborted", () => reject(new ApiError(400, "invalid_request", "Request aborted")));
  });
}
function bearer(req: IncomingMessage): string {
  const m = /^Bearer (\S{1,512})$/u.exec(req.headers.authorization ?? "");
  if (!m) unauthenticated();
  return m[1];
}
function decode(value: string): string { try { return decodeURIComponent(value); } catch { throw new ApiError(400, "invalid_request", "Invalid URL encoding"); } }
function identifier(value: string): string { const id = decode(value); try { assertId(id, "workspaceId"); } catch { invalid("Invalid identifier"); } return id; }
function integer(value: string | null, field: string, fallback?: number): number {
  if (value === null && fallback !== undefined) return fallback;
  if (value === null || !/^(0|[1-9][0-9]*)$/u.test(value) || !Number.isSafeInteger(Number(value))) invalid(`Invalid ${field}`);
  return Number(value);
}
function parameter(url: URL, name: string): string | null {
  if (url.searchParams.getAll(name).length > 1) throw new ApiError(400, "invalid_request", `Duplicate ${name}`);
  return url.searchParams.get(name);
}
function ifMatch(req: IncomingMessage): number {
  const value = req.headers["if-match"];
  if (typeof value !== "string") throw new ApiError(400, "invalid_request", "If-Match is required");
  const m = value.match(/^(?:"(0|[1-9][0-9]*)"|(0|[1-9][0-9]*))$/u);
  if (!m || !Number.isSafeInteger(Number(m[1] ?? m[2]))) throw new ApiError(400, "invalid_request", "Invalid If-Match");
  return Number(m[1] ?? m[2]);
}
function documentPath(value: string): string {
  const path = decode(value), result = validateWorkspacePath(path);
  if (!result.ok) invalid(`Invalid document path: ${result.reason}`);
  return path;
}

export function createTeamServer(store: TeamDatabase, options: ServerOptions): Server | SecureServer {
  const clock = options.now ?? Date.now;
  store.db.prepare("DELETE FROM idempotency WHERE created_at<=?").run(clock() - 24 * 60 * 60 * 1000);
  const handler = async (req: IncomingMessage, res: import("node:http").ServerResponse) => {
    const started = Date.now(), method = req.method ?? "GET";
    let route = "not_found", reply: Reply;
    try {
      const target = req.url ?? "/";
      if (!target.startsWith("/") || target.startsWith("//") || target.includes("#")) throw new ApiError(400, "invalid_request", "Invalid request target");
      const rawPath = target.split("?")[0], url = new URL(target, "http://localhost");
      const body = ["POST", "PUT", "DELETE", "PATCH"].includes(method) ? await readBody(req) : {};
      const now = clock();
      // A Key presented on an admin route is a valid credential for the wrong audience: 403, not 401.
      const admin = () => { const t = bearer(req); if (!isAdmin(options.adminToken, t)) { if (findWorkspaceByKey(store, t)) forbidden(); unauthenticated(); } };
      const keyed = (workspaceId?: string) => {
        const found = findWorkspaceByKey(store, bearer(req));
        if (!found) unauthenticated();
        if (found.archived) throw new ApiError(410, "workspace_archived", "Workspace is archived");
        if (workspaceId !== undefined && found.workspaceId !== workspaceId) forbidden();
        return found.workspaceId;
      };
      if (rawPath === "/api/healthz" && method === "GET") {
        route = "healthz";
        const n = (store.db.prepare("SELECT count(*) AS n FROM workspace WHERE archived_at IS NULL").get() as { n: number }).n;
        reply = { status: 200, body: { ok: true, schemaVersion: CURRENT_SCHEMA_VERSION, workspaceCount: n } };
      } else if (rawPath === "/api/connect" && method === "POST") {
        route = "connect"; reply = { status: 200, body: { workspace: getWorkspace(store, keyed()) } };
      } else if (rawPath === "/api/workspaces" && method === "POST") {
        route = "workspaces.create"; admin();
        if (req.headers["idempotency-key"] !== undefined) invalid("Workspace creation does not support Idempotency-Key");
        reply = { status: 201, body: createWorkspace(store, body, now) };
      } else if (rawPath === "/api/workspaces" && method === "GET") {
        route = "workspaces.list"; admin(); reply = { status: 200, body: { workspaces: listWorkspaces(store) } };
      } else {
        const match = rawPath.match(/^\/api\/workspaces\/([^/]+)(\/.*)?$/u);
        if (!match) notFound();
        const workspaceId = identifier(match[1]), suffix = match[2] ?? "";
        if (suffix === "" && method === "GET") { route = "workspaces.get"; admin(); reply = { status: 200, body: { workspace: getWorkspace(store, workspaceId) } }; }
        else if (suffix === "/key" && method === "GET") { route = "workspaces.key"; admin(); getWorkspace(store, workspaceId); reply = { status: 200, body: { key: getWorkspaceKey(store, workspaceId) } }; }
        else if (suffix === "" && method === "PATCH") { route = "workspaces.rename"; admin(); reply = { status: 200, body: { workspace: renameWorkspace(store, workspaceId, body) } }; }
        else if (suffix === "" && method === "DELETE") { route = "workspaces.archive"; admin(); archiveWorkspace(store, workspaceId, now); reply = { status: 200, body: { archived: true } }; }
        else if (suffix === "/changes" && method === "GET") {
          route = "changes.list"; keyed(workspaceId);
          const since = integer(parameter(url, "since"), "since", 0), limit = integer(parameter(url, "limit"), "limit", 200);
          if (limit < 1 || limit > 500) invalid("Invalid limit");
          reply = { status: 200, body: getChanges(store, { workspaceId, since, limit }) };
        } else if (suffix.startsWith("/documents/") && ["GET", "PUT", "DELETE"].includes(method)) {
          route = `documents.${method.toLowerCase()}`; keyed(workspaceId);
          const path = documentPath(suffix.slice("/documents/".length));
          if (method === "GET") {
            const requested = parameter(url, "version"), version = requested === null ? undefined : integer(requested, "version");
            if (version === 0) invalid("Invalid version");
            const doc = getDocument(store, { workspaceId, path, version }); if (!doc) notFound();
            reply = { status: 200, body: doc };
          } else {
            const expectedVersion = ifMatch(req);
            if (method === "PUT" && typeof body.content !== "string") invalid("content must be a string");
            if (method === "PUT" && Buffer.byteLength(body.content as string) > 1024 * 1024) throw new ApiError(413, "too_large", "Document is too large");
            reply = store.transaction(() => idempotentMutation(store, workspaceId, req.headers["idempotency-key"],
              { method, path: rawPath, ifMatch: req.headers["if-match"], body }, now,
              () => ({ status: 200, body: method === "DELETE" ? deleteDocument(store, { workspaceId, path, expectedVersion }) : writeDocument(store, { workspaceId, path, content: body.content as string, expectedVersion }) })));
          }
        } else notFound();
      }
    } catch (error) {
      let failure: ApiError;
      if (error instanceof ApiError) failure = error;
      else if (error instanceof DocumentConflictError) failure = new ApiError(409, "conflict", error.message, { currentVersion: error.currentVersion, currentHash: error.currentHash });
      else if (error instanceof Error && /^invalid /iu.test(error.message)) failure = new ApiError(422, "validation_failed", error.message);
      else if (error instanceof Error && error.message === "document not found") failure = new ApiError(404, "not_found", "Document not found");
      else failure = new ApiError(500, "internal_error", "Internal server error");
      reply = { status: failure.status, body: { error: { code: failure.code, message: failure.message, ...(failure.details === undefined ? {} : { details: failure.details }) } } };
    }
    res.writeHead(reply.status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff" });
    res.end(JSON.stringify(reply.body));
    try { options.logger?.({ event: "api_request", method, route, status: reply.status, durationMs: Date.now() - started }); }
    catch { process.stderr.write("Workbench request logger failed\n"); }
  };
  const tuning = { requestTimeout: 5000, headersTimeout: 5000, keepAliveTimeout: 1000, maxHeaderSize: 16384 };
  // TLS is opt-in; without it the server stays plain HTTP and must not be exposed publicly.
  return options.tls
    ? createSecureServer({ ...tuning, cert: readFileSync(options.tls.cert), key: readFileSync(options.tls.key) }, handler)
    : createServer(tuning, handler);
}
