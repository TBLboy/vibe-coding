import { randomUUID } from "node:crypto";
import type { TeamDatabase } from "../store/sqlite.ts";
import { ApiError, invalid, notFound, text } from "../http/errors.ts";
import { writeDocument } from "./documents.ts";
import { issueWorkspaceKey } from "./key.ts";
import { validateWorkspacePath } from "./paths.ts";
import { validText, pathsCollide, MAX_DOCUMENT_BYTES } from "../../shared/team-contracts/limits.ts";
import { DEFAULT_TYPE, getTemplate } from "../templates/registry.ts";

export interface WorkspaceInfo { id: string; name: string; type: string; createdAt: string }

interface Row { id: string; name: string; type: string; created_at: string }
const info = (r: Row): WorkspaceInfo => ({ id: r.id, name: r.name, type: r.type, createdAt: r.created_at });

export function getWorkspace(store: TeamDatabase, id: string): WorkspaceInfo {
  const row = store.db.prepare("SELECT id,name,type,created_at FROM workspace WHERE id=? AND archived_at IS NULL").get(id) as Row | undefined;
  if (!row) notFound();
  return info(row);
}

/** Creates the workspace, its Key and the type template files in one transaction. */
export function createWorkspace(store: TeamDatabase, body: Record<string, unknown>, now: number, importing = false): { workspace: WorkspaceInfo; key: string } {
  const name = text(body.name, "name", 100);
  const type = body.type === undefined ? DEFAULT_TYPE : body.type;
  if (typeof type !== "string") invalid("Invalid type");
  const pack = getTemplate(type);
  if (!pack) throw new ApiError(422, "unsupported_type", `Unsupported workspace type: ${type}`);
  let files=pack.files;
  if(importing){
    if(body.type===undefined||!Array.isArray(body.files)||!body.files.length)invalid('Invalid import files or type');
    const seen=new Set<string>();files=[];
    for(const item of body.files){
      if(!item||typeof item!=='object'||Array.isArray(item)||typeof item.path!=='string'||!validateWorkspacePath(item.path).ok||typeof item.content!=='string'||!validText(item.content)||seen.has(item.path)||[...seen].some(p=>pathsCollide(p,item.path)))invalid('Invalid import file or path collision');
      if(Buffer.byteLength(item.content)>MAX_DOCUMENT_BYTES)throw new ApiError(413,'too_large','Document is too large');
      seen.add(item.path);files.push({path:item.path,content:item.content});
    }
    if(!seen.has('AGENTS.md')||!seen.has('.vibe/progress.md'))invalid('Invalid import: AGENTS.md and .vibe/progress.md required');
  }
  const id = `ws_${randomUUID()}`, iso = new Date(now).toISOString();
  return store.transaction((db) => {
    db.prepare("INSERT INTO org (id,name,created_at) VALUES ('single','single',?) ON CONFLICT(id) DO NOTHING").run(iso);
    db.prepare("INSERT INTO workspace (id,org_id,name,slug,created_by,created_at,type) VALUES (?,?,?,?,?,?,?)")
      .run(id, "single", name, id, "admin", iso, type);
    db.prepare("INSERT INTO workspace_seq (workspace_id,seq) VALUES (?,0)").run(id);
    const key = issueWorkspaceKey(store, id, now);
    for (const f of files) writeDocument(store, { workspaceId: id, path: f.path, content: f.content, expectedVersion: 0, now: iso });
    return { workspace: getWorkspace(store, id), key };
  });
}

export function listWorkspaces(store: TeamDatabase): WorkspaceInfo[] {
  const rows = store.db.prepare("SELECT id,name,type,created_at FROM workspace WHERE archived_at IS NULL ORDER BY created_at,id").all() as unknown as Row[];
  return rows.map(info);
}

export function renameWorkspace(store: TeamDatabase, id: string, body: Record<string, unknown>): WorkspaceInfo {
  const name = text(body.name, "name", 100);
  getWorkspace(store, id);
  store.db.prepare("UPDATE workspace SET name=? WHERE id=?").run(name, id);
  return getWorkspace(store, id);
}

/** Archive: data is kept, the Key stops working (findWorkspaceByKey reports archived). */
export function archiveWorkspace(store: TeamDatabase, id: string, now: number): void {
  getWorkspace(store, id);
  store.db.prepare("UPDATE workspace SET archived_at=? WHERE id=?").run(new Date(now).toISOString(), id);
}

export function getWorkspaceKeyHint(store: TeamDatabase, id: string): { exists: boolean } {
  getWorkspace(store, id);
  return { exists: store.db.prepare("SELECT 1 FROM workspace_key WHERE workspace_id=?").get(id) !== undefined };
}
