import type { TeamDatabase } from "../store/sqlite.ts";
import type { WorkspaceAuth } from "./access.ts";
import { workspaceTasks, type TeamTask, type TaskStatus } from "./tasks.ts";

export function touchPresence(store:TeamDatabase,workspaceId:string,accountId:string,now:number): void {
  store.db.prepare(`INSERT INTO presence (workspace_id,account_id,last_seen_at)
    SELECT m.workspace_id,m.account_id,? FROM membership m JOIN account a ON a.id=m.account_id
    WHERE m.workspace_id=? AND m.account_id=? AND m.status='active' AND a.disabled_at IS NULL
    ON CONFLICT(workspace_id,account_id) DO UPDATE SET last_seen_at=MAX(last_seen_at,excluded.last_seen_at)`)
    .run(now,workspaceId,accountId);
}
export function getBoard(store:TeamDatabase,auth:WorkspaceAuth,now:number) {
  return store.transaction(db=>{
    touchPresence(store,auth.workspaceId,auth.account.id,now);
    const tasks:Record<TaskStatus,TeamTask[]>={open:[],claimed:[],done:[],abandoned:[]};
    const all=workspaceTasks(store,auth.workspaceId);
    for(const task of all)tasks[task.status].push(task);
    const rows=db.prepare(`SELECT m.account_id,a.display_name,m.role,p.last_seen_at FROM membership m
      JOIN account a ON a.id=m.account_id LEFT JOIN presence p ON p.workspace_id=m.workspace_id AND p.account_id=m.account_id
      WHERE m.workspace_id=? AND m.status='active' AND a.disabled_at IS NULL ORDER BY m.created_at,m.account_id`)
      .all(auth.workspaceId) as unknown as {account_id:string;display_name:string;role:string;last_seen_at:number|null}[];
    const members=rows.map(row=>({accountId:row.account_id,displayName:row.display_name,role:row.role,
      online:row.last_seen_at!==null && now-row.last_seen_at<300000,
      lastSeenAt:row.last_seen_at===null?null:new Date(row.last_seen_at).toISOString(),
      currentTaskId:tasks.claimed.find(task=>task.claimedBy===row.account_id)?.id??null}));
    const recentChanges=db.prepare(`SELECT c.seq,c.path,c.op,c.version,c.created_at AS at,v.author AS by
      FROM change c JOIN document d ON d.workspace_id=c.workspace_id AND d.path=c.path
      JOIN document_version v ON v.document_id=d.id AND v.version=c.version
      WHERE c.workspace_id=? ORDER BY c.seq DESC LIMIT 50`).all(auth.workspaceId).map(row=>({...row}));
    return {members,tasks,recentChanges};
  });
}
export type Board = ReturnType<typeof getBoard>;
