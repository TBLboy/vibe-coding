import { randomUUID } from "node:crypto";
import type { TeamDatabase } from "../store/sqlite.ts";
import type { Account } from "./identity.ts";
import { createTaskKey } from "./access.ts";
import { bodyObject, invalid, notFound, text } from "../http/errors.ts";

export interface WorkspaceInfo { id:string; orgId:string; name:string; ownerAccountId:string; repos:{url:string;branch:string}[]; seq:number }
export function workspaceInfo(store:TeamDatabase, orgId:string, id:string): WorkspaceInfo {
  const row=store.db.prepare("SELECT id,org_id,name,created_by FROM workspace WHERE id=? AND org_id=? AND archived_at IS NULL")
    .get(id,orgId) as {id:string;org_id:string;name:string;created_by:string}|undefined;
  if(!row) notFound();
  const repos=store.db.prepare("SELECT url,branch FROM workspace_repo WHERE workspace_id=? ORDER BY is_primary DESC,id")
    .all(id) as unknown as {url:string;branch:string}[];
  const sequence=store.db.prepare("SELECT seq FROM workspace_seq WHERE workspace_id=?").get(id) as {seq:number}|undefined;
  return {id:row.id,orgId:row.org_id,name:row.name,ownerAccountId:row.created_by,repos:repos.map(r=>({...r})),seq:sequence?.seq??0};
}
export function createWorkspace(store:TeamDatabase, account:Account, body:Record<string,unknown>, now:number): {workspace:WorkspaceInfo; taskKey:string} {
  const name=text(body.name,"name",100);
  if(!Array.isArray(body.repos) || body.repos.length<1 || body.repos.length>20) invalid("Provide 1 to 20 repositories");
  const repos=body.repos.map(value=>{
    const repo=bodyObject(value), url=text(repo.url,"repository URL",2048), branch=text(repo.branch,"branch",255);
    if(url.includes("://")) {
      let parsed:URL; try {parsed=new URL(url);} catch {invalid("Invalid repository URL");}
      if(!["https:","http:","ssh:","git:"].includes(parsed.protocol) || !parsed.hostname || parsed.password ||
        ((parsed.protocol==="https:" || parsed.protocol==="http:") && parsed.username)) invalid("Invalid repository URL or embedded credentials");
    } else if(!/^[^\s@]+@[^\s:]+:.+$/u.test(url)) invalid("Invalid repository URL");
    return {url,branch};
  });
  const id=`ws_${randomUUID()}`;
  return store.transaction(db=>{
    db.prepare("INSERT INTO workspace (id,org_id,name,slug,created_by,created_at) VALUES (?,?,?,?,?,?)")
      .run(id,account.orgId,name,id,account.id,new Date(now).toISOString());
    db.prepare("INSERT INTO membership (workspace_id,account_id,role,status,created_at,decided_at) VALUES (?,?,'owner','active',?,?)")
      .run(id,account.id,now,now);
    db.prepare("INSERT INTO workspace_seq (workspace_id,seq) VALUES (?,0)").run(id);
    repos.forEach((repo,i)=>db.prepare("INSERT INTO workspace_repo (id,workspace_id,url,branch,is_primary) VALUES (?,?,?,?,?)")
      .run(`repo_${randomUUID()}`,id,repo.url,repo.branch,i===0?1:0));
    const taskKey=createTaskKey(store,id,now,null);
    return {workspace:workspaceInfo(store,account.orgId,id),taskKey};
  });
}
export function listWorkspaces(store:TeamDatabase, account:Account): (WorkspaceInfo & {role:"owner"|"member"})[] {
  const rows=store.db.prepare(`SELECT w.id,m.role FROM membership m JOIN workspace w ON w.id=m.workspace_id
    WHERE m.account_id=? AND m.status='active' AND w.org_id=? AND w.archived_at IS NULL ORDER BY w.created_at,w.id`)
    .all(account.id,account.orgId) as unknown as {id:string;role:"owner"|"member"}[];
  return rows.map(row=>({...workspaceInfo(store,account.orgId,row.id),role:row.role}));
}
