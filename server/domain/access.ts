import { randomUUID } from "node:crypto";
import type { TeamDatabase } from "../store/sqlite.ts";
import { type Account, authenticateSession, hashToken, issueSecret, WORKSPACE_TTL_MS } from "./identity.ts";
import { forbidden, invalid, unauthenticated } from "../http/errors.ts";

export interface WorkspaceAuth { account: Account; workspaceId: string; role: "owner"|"member" }
export function requireOwner(auth: WorkspaceAuth): void { if(auth.role!=="owner") forbidden(); }

export function expiry(value: unknown, now:number): number|null {
  if (value===undefined || value===null) return null;
  if (typeof value!=="string") invalid("Invalid expiresAt");
  const timestamp=Date.parse(value);
  if (!Number.isFinite(timestamp) || timestamp<=now) invalid("expiresAt must be in the future");
  return timestamp;
}
export function createTaskKey(store:TeamDatabase, workspaceId:string, now:number, expiresAt:number|null): string {
  const key=issueSecret(24);
  store.db.prepare("INSERT INTO task_key (id,workspace_id,secret_hash,created_at,expires_at) VALUES (?,?,?,?,?)")
    .run(`key_${randomUUID()}`,workspaceId,hashToken(key),now,expiresAt);
  return key;
}
export function rotateTaskKey(store:TeamDatabase, auth:WorkspaceAuth, expiresAt:unknown, now:number): string {
  requireOwner(auth); const until=expiry(expiresAt,now);
  return store.transaction(db=>{
    db.prepare("UPDATE task_key SET revoked_at=? WHERE workspace_id=? AND revoked_at IS NULL").run(now,auth.workspaceId);
    return createTaskKey(store,auth.workspaceId,now,until);
  });
}

export function connectWorkspace(store:TeamDatabase, orgId:string, sessionToken:string, key:unknown, now:number): {workspaceToken:string; workspaceId:string; role:"owner"|"member"} {
  if(typeof key!=="string" || !/^[A-Za-z0-9_-]{32}$/u.test(key)) unauthenticated();
  return store.transaction(db=>{
    // A key grants no identity: a separately authenticated active account is mandatory.
    const found=db.prepare(`SELECT k.workspace_id FROM task_key k JOIN workspace w ON w.id=k.workspace_id
      WHERE k.secret_hash=? AND k.revoked_at IS NULL AND (k.expires_at IS NULL OR k.expires_at>?)
      AND w.org_id=? AND w.archived_at IS NULL`).get(hashToken(key),now,orgId) as {workspace_id:string}|undefined;
    if(!found) unauthenticated();
    const account=authenticateSession(store,orgId,sessionToken,now);
    const membership=db.prepare("SELECT role,status FROM membership WHERE workspace_id=? AND account_id=?")
      .get(found.workspace_id,account.id) as {role:"owner"|"member";status:string}|undefined;
    if(membership?.status!=="active") forbidden();
    const workspaceToken=issueSecret();
    db.prepare("INSERT INTO workspace_token (token_hash,workspace_id,account_id,created_at,expires_at) VALUES (?,?,?,?,?)")
      .run(hashToken(workspaceToken),found.workspace_id,account.id,now,now+WORKSPACE_TTL_MS);
    return {workspaceToken,workspaceId:found.workspace_id,role:membership.role};
  });
}

export function authenticateWorkspace(store:TeamDatabase, orgId:string, token:string, workspaceId:string, now:number): WorkspaceAuth {
  const row=store.db.prepare(`SELECT a.id,a.org_id,a.email,a.display_name,a.disabled_at,t.workspace_id,t.revoked_at,
      m.role,m.status,w.archived_at FROM workspace_token t
      JOIN account a ON a.id=t.account_id JOIN workspace w ON w.id=t.workspace_id
      JOIN membership m ON m.workspace_id=t.workspace_id AND m.account_id=t.account_id
      WHERE t.token_hash=? AND t.expires_at>? AND a.org_id=? AND w.org_id=?`)
    .get(hashToken(token),now,orgId,orgId) as {
      id:string;org_id:string;email:string;display_name:string;disabled_at:string|null;workspace_id:string;
      revoked_at:number|null;role:"owner"|"member";status:string;archived_at:string|null;
    }|undefined;
  if(!row || row.disabled_at!==null) unauthenticated();
  if(row.workspace_id!==workspaceId || row.status!=="active" || row.archived_at!==null) forbidden();
  if(row.revoked_at!==null) unauthenticated();
  return {account:{id:row.id,orgId:row.org_id,email:row.email,displayName:row.display_name},workspaceId,role:row.role};
}
