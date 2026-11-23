import { randomUUID } from "node:crypto";
import type { TeamDatabase } from "../store/sqlite.ts";
import { type Account, normalizeEmail } from "./identity.ts";
import { type WorkspaceAuth, requireOwner } from "./access.ts";
import { conflict, forbidden, invalid, notFound } from "../http/errors.ts";

function assertWorkspace(store:TeamDatabase, workspaceId:string, orgId:string): void {
  if(!store.db.prepare("SELECT id FROM workspace WHERE id=? AND org_id=? AND archived_at IS NULL").get(workspaceId,orgId)) notFound();
}
export function inviteMember(store:TeamDatabase, auth:WorkspaceAuth, body:Record<string,unknown>, now:number): {id:string;workspaceId:string;email:string;status:string} {
  requireOwner(auth); const email=normalizeEmail(body.email);
  if(body.role!==undefined && body.role!=="member") invalid("Invitations can only grant member role");
  return store.transaction(db=>{
    const target=db.prepare("SELECT id FROM account WHERE org_id=? AND email=? AND disabled_at IS NULL")
      .get(auth.account.orgId,email) as {id:string}|undefined;
    if(target) {
      const existing=db.prepare("SELECT status FROM membership WHERE workspace_id=? AND account_id=?").get(auth.workspaceId,target.id) as {status:string}|undefined;
      if(existing?.status==="active") conflict("Account is already an active member");
      db.prepare(`INSERT INTO membership (workspace_id,account_id,role,status,invited_by,created_at) VALUES (?,?,'member','invited',?,?)
        ON CONFLICT(workspace_id,account_id) DO UPDATE SET role='member',status='invited',invited_by=excluded.invited_by,decided_at=NULL`)
        .run(auth.workspaceId,target.id,auth.account.id,now);
    }
    const id=`invite_${randomUUID()}`;
    db.prepare(`INSERT INTO invitation (id,workspace_id,org_id,email,role,status,created_by,created_at) VALUES (?,?,?,?,'member','pending',?,?)
      ON CONFLICT(workspace_id,email) DO UPDATE SET status='pending',created_by=excluded.created_by,created_at=excluded.created_at,decided_at=NULL`)
      .run(id,auth.workspaceId,auth.account.orgId,email,auth.account.id,now);
    const row=db.prepare("SELECT id FROM invitation WHERE workspace_id=? AND email=?").get(auth.workspaceId,email) as {id:string};
    return {id:row.id,workspaceId:auth.workspaceId,email,status:"pending"};
  });
}
export function acceptInvitation(store:TeamDatabase, account:Account, workspaceId:string, now:number): {status:"active"} {
  return store.transaction(db=>{
    assertWorkspace(store,workspaceId,account.orgId);
    const invite=db.prepare("SELECT id,created_by FROM invitation WHERE workspace_id=? AND org_id=? AND email=? AND status='pending'")
      .get(workspaceId,account.orgId,account.email) as {id:string;created_by:string}|undefined;
    if(!invite) notFound();
    const existing=db.prepare("SELECT status FROM membership WHERE workspace_id=? AND account_id=?").get(workspaceId,account.id) as {status:string}|undefined;
    if(existing?.status==="active") conflict("Already active");
    db.prepare(`INSERT INTO membership (workspace_id,account_id,role,status,invited_by,created_at,decided_at) VALUES (?,?,'member','active',?,?,?)
      ON CONFLICT(workspace_id,account_id) DO UPDATE SET role='member',status='active',decided_at=excluded.decided_at`)
      .run(workspaceId,account.id,invite.created_by,now,now);
    db.prepare("UPDATE invitation SET status='accepted',decided_at=? WHERE id=?").run(now,invite.id);
    return {status:"active"};
  });
}
export function requestMembership(store:TeamDatabase, account:Account, workspaceId:string, body:Record<string,unknown>, now:number): {status:"requested"} {
  if(body.role!==undefined) invalid("Membership requests cannot choose a role");
  return store.transaction(db=>{
    assertWorkspace(store,workspaceId,account.orgId);
    const existing=db.prepare("SELECT status FROM membership WHERE workspace_id=? AND account_id=?").get(workspaceId,account.id) as {status:string}|undefined;
    if(existing && existing.status!=="removed") conflict("Membership is already active or pending");
    db.prepare(`INSERT INTO membership (workspace_id,account_id,role,status,created_at) VALUES (?,?,'member','requested',?)
      ON CONFLICT(workspace_id,account_id) DO UPDATE SET role='member',status='requested',invited_by=NULL,decided_at=NULL`)
      .run(workspaceId,account.id,now);
    return {status:"requested"};
  });
}
export function decideMembership(store:TeamDatabase, auth:WorkspaceAuth, accountId:string, approve:unknown, now:number): {status:string} {
  requireOwner(auth); if(typeof approve!=="boolean") invalid("approve must be boolean");
  const status=approve?"active":"removed";
  const result=store.db.prepare("UPDATE membership SET status=?,decided_at=? WHERE workspace_id=? AND account_id=? AND status='requested'")
    .run(status,now,auth.workspaceId,accountId);
  if(result.changes===0) conflict("No pending application for this account");
  return {status};
}
export function removeMember(store:TeamDatabase, auth:WorkspaceAuth, accountId:string, now:number): {status:"removed"} {
  requireOwner(auth);
  return store.transaction(db=>{
    const member=db.prepare("SELECT role,status FROM membership WHERE workspace_id=? AND account_id=?").get(auth.workspaceId,accountId) as {role:string;status:string}|undefined;
    if(!member) notFound();
    if(member.role==="owner" && member.status==="active") {
      const owners=db.prepare("SELECT count(*) AS n FROM membership WHERE workspace_id=? AND role='owner' AND status='active'").get(auth.workspaceId) as {n:number};
      if(owners.n<=1) conflict("Cannot remove the sole active owner");
    }
    db.prepare("UPDATE membership SET status='removed',decided_at=? WHERE workspace_id=? AND account_id=?").run(now,auth.workspaceId,accountId);
    db.prepare("UPDATE workspace_token SET revoked_at=? WHERE workspace_id=? AND account_id=? AND revoked_at IS NULL").run(now,auth.workspaceId,accountId);
    db.prepare(`UPDATE invitation SET status='revoked',decided_at=? WHERE workspace_id=? AND email=(SELECT email FROM account WHERE id=?) AND status='pending'`)
      .run(now,auth.workspaceId,accountId);
    return {status:"removed"};
  });
}
export function listMembers(store:TeamDatabase, auth:WorkspaceAuth): unknown[] {
  return store.db.prepare(`SELECT m.account_id AS accountId,a.email,a.display_name AS displayName,m.role,m.status
    FROM membership m JOIN account a ON a.id=m.account_id WHERE m.workspace_id=? ORDER BY m.created_at,m.account_id`)
    .all(auth.workspaceId).map(row=>({...row}));
}
