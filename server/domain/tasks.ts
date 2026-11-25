import { randomUUID } from "node:crypto";
import type { TeamDatabase } from "../store/sqlite.ts";
import type { WorkspaceAuth } from "./access.ts";
import { normalizeScope, findScopeOverlaps, type ScopeOverlap } from "./task-scope.ts";
import { ApiError, forbidden, invalid, notFound, text } from "../http/errors.ts";
import { getDocument, writeDocument } from "./documents.ts";

export type TaskStatus = "open"|"claimed"|"done"|"abandoned";
export interface TeamTask {
  id:string; workspaceId:string; title:string; note:string|null; scope:string[]; status:TaskStatus;
  declaredBy:string; claimedBy:string|null; createdAt:string; updatedAt:string; closedReason:string|null;
}
interface TaskRow {
  id:string; workspace_id:string; title:string; note:string|null; scope_json:string; status:TaskStatus;
  declared_by:string; claimed_by:string|null; created_at:number; updated_at:number; closed_reason:string|null;
}
function mapTask(row:TaskRow): TeamTask {
  return {id:row.id,workspaceId:row.workspace_id,title:row.title,note:row.note,scope:JSON.parse(row.scope_json),status:row.status,
    declaredBy:row.declared_by,claimedBy:row.claimed_by,createdAt:new Date(row.created_at).toISOString(),
    updatedAt:new Date(row.updated_at).toISOString(),closedReason:row.closed_reason};
}
export function workspaceTasks(store:TeamDatabase, workspaceId:string): TeamTask[] {
  return (store.db.prepare("SELECT * FROM task WHERE workspace_id=? ORDER BY updated_at DESC, rowid DESC")
    .all(workspaceId) as unknown as TaskRow[]).map(mapTask);
}
function taskById(store:TeamDatabase, workspaceId:string, id:string): TeamTask {
  const row=store.db.prepare("SELECT * FROM task WHERE workspace_id=? AND id=?").get(workspaceId,id) as unknown as TaskRow|undefined;
  if(!row) notFound(); return mapTask(row);
}
function activeActor(store:TeamDatabase, auth:WorkspaceAuth): void {
  if(!store.db.prepare(`SELECT m.account_id FROM membership m JOIN account a ON a.id=m.account_id
    JOIN workspace w ON w.id=m.workspace_id WHERE m.workspace_id=? AND m.account_id=? AND m.status='active'
    AND a.disabled_at IS NULL AND a.org_id=? AND w.org_id=? AND w.archived_at IS NULL`)
    .get(auth.workspaceId,auth.account.id,auth.account.orgId,auth.account.orgId)) forbidden();
}
function mirrorTask(store:TeamDatabase, task:TeamTask, actor:string): void {
  const path=`work/${task.id}.json`, previous=getDocument(store,{workspaceId:task.workspaceId,path});
  writeDocument(store,{workspaceId:task.workspaceId,path,content:JSON.stringify(task),accountId:actor,
    ownerAccountId:task.declaredBy,expectedVersion:previous?.version??0,now:task.updatedAt});
}
function claimConflict(task:TeamTask): never {
  throw new ApiError(409,"conflict","Task is not available for this operation",{claimedBy:task.claimedBy,status:task.status});
}

export function declareTask(store:TeamDatabase,auth:WorkspaceAuth,body:Record<string,unknown>,now:number): {
  task:TeamTask;overlapWarnings:{taskId:string;overlaps:ScopeOverlap[]}[];
} {
  const title=text(body.title,"title",200), note=body.note===undefined?null:text(body.note,"note",4000);
  let scope:string[];
  try {scope=normalizeScope((body.scope===undefined?[]:body.scope) as string[]);} catch {invalid("Invalid task scope");}
  return store.transaction(db=>{
    activeActor(store,auth);
    const overlapWarnings=workspaceTasks(store,auth.workspaceId).flatMap(task=>{
      const overlaps=findScopeOverlaps(scope,task.scope);return overlaps.length?[{taskId:task.id,overlaps}]:[];
    });
    const id=`task_${randomUUID()}`;
    db.prepare(`INSERT INTO task (id,workspace_id,title,note,scope_json,status,declared_by,created_at,updated_at)
      VALUES (?,?,?,?,?,'open',?,?,?)`).run(id,auth.workspaceId,title,note,JSON.stringify(scope),auth.account.id,now,now);
    const task=taskById(store,auth.workspaceId,id);mirrorTask(store,task,auth.account.id);
    return {task,overlapWarnings};
  });
}
export function claimTask(store:TeamDatabase,auth:WorkspaceAuth,id:string,now:number): TeamTask {
  return store.transaction(db=>{
    activeActor(store,auth);
    const result=db.prepare(`UPDATE task SET status='claimed',claimed_by=?,updated_at=?,closed_reason=NULL
      WHERE workspace_id=? AND id=? AND status IN ('open','abandoned') AND claimed_by IS NULL`)
      .run(auth.account.id,now,auth.workspaceId,id);
    const task=taskById(store,auth.workspaceId,id);
    if(result.changes!==1) claimConflict(task);
    mirrorTask(store,task,auth.account.id);return task;
  });
}
export function updateTask(store:TeamDatabase,auth:WorkspaceAuth,id:string,body:Record<string,unknown>,now:number): TeamTask {
  if(body.status!=="done" && body.status!=="abandoned") invalid("status must be done or abandoned");
  const status=body.status;
  const reason=body.status==="abandoned" || body.reason!==undefined?text(body.reason,"reason",4000):null;
  return store.transaction(db=>{
    activeActor(store,auth);const current=taskById(store,auth.workspaceId,id);
    if(current.status!=="claimed") claimConflict(current);
    if(current.claimedBy!==auth.account.id) forbidden();
    db.prepare(`UPDATE task SET status=?,claimed_by=?,closed_reason=?,updated_at=?
      WHERE workspace_id=? AND id=? AND status='claimed' AND claimed_by=?`)
      .run(status,status==="done"?auth.account.id:null,reason,now,auth.workspaceId,id,auth.account.id);
    const task=taskById(store,auth.workspaceId,id);mirrorTask(store,task,auth.account.id);return task;
  });
}
/** Called inside the membership removal transaction, not a separate commit. */
export function releaseMemberTasks(store:TeamDatabase,workspaceId:string,accountId:string,actor:string,now:number): void {
  for(const current of workspaceTasks(store,workspaceId).filter(task=>task.status==="claimed" && task.claimedBy===accountId)) {
    store.db.prepare("UPDATE task SET status='open',claimed_by=NULL,closed_reason='Member removed',updated_at=? WHERE workspace_id=? AND id=?")
      .run(now,workspaceId,current.id);
    mirrorTask(store,taskById(store,workspaceId,current.id),actor);
  }
}
