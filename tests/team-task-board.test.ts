import assert from "node:assert/strict";
import test from "node:test";
import type { AddressInfo } from "node:net";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { openTeamDatabase, applyMigrations } from "../server/store/sqlite.ts";
import { MIGRATIONS, CURRENT_SCHEMA_VERSION } from "../server/store/schema.ts";
import { createWorkspace } from "../server/domain/workspace.ts";
import { declareTask, claimTask, updateTask } from "../server/domain/tasks.ts";
import { createAccount } from "../server/domain/identity.ts";
import { createTeamServer } from "../server/http/router.ts";

async function harness(t:{after(fn:()=>Promise<void>):void}) {
  const store=openTeamDatabase(":memory:"), orgId="org_board", password="board test password";
  const owner=await createAccount(store,{orgId,email:"owner@example.test",displayName:"Owner",password});
  const alice=await createAccount(store,{orgId,email:"alice@example.test",displayName:"<Alice & Co>",password});
  let now=Date.parse("2026-11-23T12:00:00Z"); const logs:unknown[]=[];
  const server=createTeamServer(store,{orgId,now:()=>now,logger:r=>logs.push(r)});
  await new Promise<void>(resolve=>server.listen(0,"127.0.0.1",resolve));
  const base=`http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  t.after(async()=>{await new Promise<void>((resolve,reject)=>server.close(e=>e?reject(e):resolve()));store.close();});
  const req=async(path:string,method="GET",token?:string,body?:unknown,headers:Record<string,string>={})=>{
    const response=await fetch(base+path,{method,headers:{...(token?{authorization:`Bearer ${token}`} : {}),...(body===undefined?{}:{"content-type":"application/json"}),...headers},...(body===undefined?{}:{body:JSON.stringify(body)})});
    return {status:response.status,body:await response.json() as any};
  };
  const login=async(email:string)=>(await req("/api/auth/login","POST",undefined,{email,password})).body.sessionToken as string;
  const os=await login("owner@example.test"), as=await login("alice@example.test");
  const w=(await req("/api/workspaces","POST",os,{name:"<Team & Workspace>",repos:[{url:"https://example.test/team.git",branch:"main"}]})).body;
  const initialSeq=1;assert.equal(w.workspace.seq,initialSeq);
  const ot=(await req("/api/connect","POST",os,{key:w.taskKey})).body.workspaceToken as string;
  const p=`/api/workspaces/${w.workspace.id}`;
  const baseline=await req(`${p}/changes?since=0`,"GET",ot);
  assert.equal(baseline.status,200);assert.equal(baseline.body.changes.length,1);
  assert.equal(baseline.body.changes[0].path,"index.json");assert.equal(baseline.body.changes[0].seq,initialSeq);
  assert.equal((await req(`${p}/invitations`,"POST",ot,{email:"alice@example.test"})).status,201);
  assert.equal((await req(`${p}/invitations/accept`,"POST",as,{})).status,200);
  const at=(await req("/api/connect","POST",as,{key:w.taskKey})).body.workspaceToken as string;
  const declare=async(title="Task",scope:string[]=[],token=at,extra:Record<string,unknown>={},headers:Record<string,string>={})=>req(`${p}/tasks`,"POST",token,{title,scope,...extra},headers);
  return {store,base,req,p,ot,at,os,as,owner,alice,w,initialSeq,logs,declare,advance:(ms:number)=>{now+=ms;},now:()=>now};
}

test("task declaration normalizes scopes, warns on existing overlap and mirrors one work document",async t=>{
  const h=await harness(t);
  const first=await h.declare("Auth",[" ./src\\auth\\ "]);assert.equal(first.status,201);assert.deepEqual(first.body.task.scope,["src/auth/"]);
  assert.equal(first.body.task.declaredBy,h.alice.id);assert.equal(first.body.task.status,"open");
  assert.equal(first.body.task.claimedBy,null);assert.deepEqual(first.body.overlapWarnings,[]);
  const next=await h.declare("Login",["src/auth/login.ts"],h.ot,{note:"review inputs",accountId:"forged",claimedBy:h.alice.id});
  assert.equal(next.status,201);assert.equal(next.body.task.declaredBy,h.owner.id);assert.equal(next.body.task.claimedBy,null);
  assert.equal(next.body.overlapWarnings[0].taskId,first.body.task.id);
  assert.deepEqual(next.body.overlapWarnings[0].overlaps,[{left:"src/auth/login.ts",right:"src/auth/",reason:"directory-prefix"}]);
  assert.deepEqual((await h.declare("Unscoped")).body.overlapWarnings,[]);
  const feed=await h.req(`${h.p}/changes?since=${h.initialSeq}`,"GET",h.at);assert.deepEqual(feed.body.changes.map((c:any)=>c.seq),[h.initialSeq+1,h.initialSeq+2,h.initialSeq+3]);
  assert.equal(feed.body.changes[0].path,`work/${first.body.task.id}.json`);
  assert.deepEqual(JSON.parse(feed.body.changes[0].content),first.body.task);
  assert.equal((await h.req(`${h.p}/documents/work/${first.body.task.id}.json`,"PUT",h.ot,{content:"forged"},{"if-match":"1"})).status,422);
});

test("exclusive HTTP claims return the holder; only holder closes, abandoned tasks can be reclaimed",async t=>{
  const h=await harness(t), id=(await h.declare()).body.task.id;
  const results=await Promise.all([h.req(`${h.p}/tasks/${id}/claim`,"POST",h.at,{}),h.req(`${h.p}/tasks/${id}/claim`,"POST",h.ot,{})]);
  assert.deepEqual(results.map(r=>r.status).sort(),[200,409]);
  const held=results.find(r=>r.status===200)!.body.task, fail=results.find(r=>r.status===409)!;
  assert.equal(fail.body.error.details.claimedBy,held.claimedBy);
  const token=held.claimedBy===h.alice.id?h.at:h.ot, other=token===h.at?h.ot:h.at;
  assert.equal((await h.req(`${h.p}/tasks/${id}/status`,"POST",other,{status:"done"})).status,403);
  assert.equal((await h.req(`${h.p}/tasks/${id}/status`,"POST",token,{status:"abandoned"})).status,422);
  const abandon=await h.req(`${h.p}/tasks/${id}/status`,"POST",token,{status:"abandoned",reason:"Needs another approach"});
  assert.equal(abandon.status,200);assert.equal(abandon.body.task.claimedBy,null);assert.equal(abandon.body.task.closedReason,"Needs another approach");
  const board=await h.req(`${h.p}/board`,"GET",other);assert.equal(board.body.tasks.abandoned[0].id,id);
  assert.equal((await h.req(`${h.p}/tasks/${id}/claim`,"POST",other,{})).status,200);
  assert.equal((await h.req(`${h.p}/tasks/${id}/status`,"POST",other,{status:"done"})).status,200);
  assert.equal((await h.req(`${h.p}/tasks/${id}/claim`,"POST",token,{})).status,409);
  const feed=(await h.req(`${h.p}/changes?since=${h.initialSeq}`,"GET",h.at)).body.changes;
  assert.deepEqual(feed.map((c:any)=>JSON.parse(c.content).status),["open","claimed","abandoned","claimed","done"]);
  assert.equal(JSON.parse(feed[2].content).closedReason,"Needs another approach");
});

test("task mutations replay once and roll back task/work/history/seq on failure",async t=>{
  const h=await harness(t), headers={"idempotency-key":"task-declare"};
  const first=await h.declare("Once",[],h.at,{},headers), again=await h.declare("Once",[],h.at,{},headers);
  assert.equal(first.status,201);assert.deepEqual(again.body,first.body);
  assert.equal((await h.declare("Other",[],h.at,{},headers)).status,409);
  const id=first.body.task.id, claimHeaders={"idempotency-key":"task-claim"};
  const claim=await h.req(`${h.p}/tasks/${id}/claim`,"POST",h.at,{},claimHeaders);
  assert.equal(claim.status,200);assert.deepEqual((await h.req(`${h.p}/tasks/${id}/claim`,"POST",h.at,{},claimHeaders)).body,claim.body);
  const before=JSON.stringify(h.store.db.prepare("SELECT * FROM task").all());
  h.store.db.exec("CREATE TRIGGER task_fail BEFORE INSERT ON change BEGIN SELECT RAISE(ABORT,'injected'); END");
  assert.equal((await h.req(`${h.p}/tasks/${id}/status`,"POST",h.at,{status:"done"})).status,500);
  assert.equal((await h.declare("Rollback")).status,500);
  assert.equal(JSON.stringify(h.store.db.prepare("SELECT * FROM task").all()),before);
  assert.equal(h.store.db.prepare("SELECT count(*) AS n FROM document_version").get()?.n,h.initialSeq+2);
  assert.equal(h.store.db.prepare("SELECT seq FROM workspace_seq WHERE workspace_id=?").get(h.w.workspace.id)?.seq,h.initialSeq+2);
  h.store.db.exec("DROP TRIGGER task_fail");
  const done=await h.req(`${h.p}/tasks/${id}/status`,"POST",h.at,{status:"done"},{"idempotency-key":"task-done"});
  assert.equal(done.status,200);
  assert.deepEqual((await h.req(`${h.p}/tasks/${id}/status`,"POST",h.at,{status:"done"},{"idempotency-key":"task-done"})).body,done.body);
});

test("member removal atomically releases claimed tasks and preserves finished attribution",async t=>{
  const h=await harness(t), id=(await h.declare("Active")).body.task.id, second=(await h.declare("Also active")).body.task.id, doneId=(await h.declare("Completed")).body.task.id;
  for(const tid of [id,second,doneId]) assert.equal((await h.req(`${h.p}/tasks/${tid}/claim`,"POST",h.at,{})).status,200);
  await h.req(`${h.p}/tasks/${doneId}/status`,"POST",h.at,{status:"done"});
  // Release iteration is newest first: fail on the older task after a newer one was updated.
  h.store.db.exec(`CREATE TRIGGER release_fail BEFORE INSERT ON change WHEN NEW.path='work/${id}.json' BEGIN SELECT RAISE(ABORT,'injected'); END`);
  assert.equal((await h.req(`${h.p}/members/${h.alice.id}`,"DELETE",h.ot)).status,500);
  assert.equal((await h.req(h.p,"GET",h.at)).status,200);
  assert.equal(h.store.db.prepare("SELECT status FROM task WHERE id=?").get(id)?.status,"claimed");
  assert.equal(h.store.db.prepare("SELECT status FROM task WHERE id=?").get(second)?.status,"claimed");
  h.store.db.exec("DROP TRIGGER release_fail");
  assert.equal((await h.req(`${h.p}/members/${h.alice.id}`,"DELETE",h.ot)).status,200);
  assert.equal((await h.req(h.p,"GET",h.at)).status,403);
  const board=(await h.req(`${h.p}/board`,"GET",h.ot)).body;
  assert.deepEqual(board.tasks.open.map((task:any)=>task.id).sort(),[id,second].sort());
  assert.equal(board.tasks.open.every((task:any)=>task.claimedBy===null),true);
  assert.equal(board.tasks.done[0].claimedBy,h.alice.id);assert.equal(board.members.some((m:any)=>m.accountId===h.alice.id),false);
  const doc=(await h.req(`${h.p}/documents/work/${id}.json`,"GET",h.ot)).body;
  assert.equal(JSON.parse(doc.content).status,"open");
  assert.equal((await h.req(`${h.p}/tasks/${id}/claim`,"POST",h.ot,{})).status,200);
});

test("board uses current presence/latest task, and recent metadata joins each immutable version",async t=>{
  const h=await harness(t), first=(await h.declare("First",[],h.ot)).body.task.id;
  await h.req(`${h.p}/tasks/${first}/claim`,"POST",h.at,{});h.advance(1);
  const second=(await h.declare("Second")).body.task.id;
  await h.req(`${h.p}/tasks/${second}/claim`,"POST",h.at,{});
  await h.req(`${h.p}/documents/specs/private.md`,"PUT",h.ot,{content:"NEVER IN BOARD"},{"if-match":"0"});
  const board=(await h.req(`${h.p}/board`,"GET",h.ot)).body;
  const member=board.members.find((m:any)=>m.accountId===h.alice.id);assert.equal(member.online,true);assert.equal(member.currentTaskId,second);
  assert.equal(board.tasks.claimed.length,2);assert.equal(JSON.stringify(board).includes("NEVER IN BOARD"),false);
  const changes=board.recentChanges;assert.equal(changes[0].seq,h.initialSeq+5);
  assert.deepEqual(changes.filter((c:any)=>c.path===`work/${first}.json`).map((c:any)=>c.by),[h.alice.id,h.owner.id]);
  h.advance(300000);const later=(await h.req(`${h.p}/board`,"GET",h.ot)).body;
  assert.equal(later.members.find((m:any)=>m.accountId===h.alice.id).online,false);
  assert.equal(later.members.find((m:any)=>m.accountId===h.owner.id).online,true);
  await h.req(`${h.p}/tasks/no_such_task/claim`,"POST",h.at,{});
  assert.equal((await h.req(`${h.p}/board`,"GET",h.ot)).body.members.find((m:any)=>m.accountId===h.alice.id).online,false);
});

test("task APIs reject malformed input, unknown tasks and cross-workspace credentials",async t=>{
  const h=await harness(t), id=(await h.declare()).body.task.id;
  for(const body of [{title:""},{title:"x".repeat(201)},{title:"Task",scope:["../escape"]},{title:"Task",scope:"src/"},{title:"Task",scope:null},{title:"Task",scope:Array(201).fill("src/")},{title:"Task",note:5}]) {
    assert.equal((await h.req(`${h.p}/tasks`,"POST",h.at,body)).status,422);
  }
  assert.equal((await h.req(`${h.p}/tasks`,"POST",undefined,{title:"No auth"})).status,401);
  assert.equal((await h.req(`${h.p}/tasks/${id}/status`,"POST",h.at,{status:"open"})).status,422);
  assert.equal((await h.req(`${h.p}/tasks/${id}/status`,"POST",h.at,{status:"done"})).status,409);
  assert.equal((await h.req(`${h.p}/tasks/missing/claim`,"POST",h.at,{})).status,404);
  const other=(await h.req("/api/workspaces","POST",h.os,{name:"Other",repos:[{url:"https://example.test/other.git",branch:"main"}]})).body;
  const token=(await h.req("/api/connect","POST",h.os,{key:other.taskKey})).body.workspaceToken;
  assert.equal((await h.req(`${h.p}/board`,"GET",token)).status,403);
  assert.equal((await h.req(`/api/workspaces/${other.workspace.id}/tasks/${id}/claim`,"POST",token,{})).status,404);
  const board=await h.req(`/api/workspaces/${other.workspace.id}/board`,"GET",token);assert.deepEqual(board.body.tasks.open,[]);
  const op=`/api/workspaces/${other.workspace.id}`;
  await h.req(`${op}/invitations`,"POST",token,{email:"alice@example.test"});await h.req(`${op}/invitations/accept`,"POST",h.as,{});
  const otherAlice=(await h.req("/api/connect","POST",h.as,{key:other.taskKey})).body.workspaceToken;
  const otherTask=(await h.req(`${op}/tasks`,"POST",otherAlice,{title:"Other scope",scope:["src/"]})).body.task.id;
  await h.req(`${op}/tasks/${otherTask}/claim`,"POST",otherAlice,{});
  assert.deepEqual((await h.declare("Not warned across workspaces",["src/"])).body.overlapWarnings,[]);
  await h.req(`${h.p}/members/${h.alice.id}`,"DELETE",h.ot);
  assert.equal((await h.req(`${op}/board`,"GET",otherAlice)).body.tasks.claimed[0].id,otherTask);
});

test("no-JS HTML board authenticates without URL secrets and escapes all untrusted text",async t=>{
  const h=await harness(t);await h.declare('<script>alert("x")</script>',["src/<img>/"],h.at,{note:'<a href="javascript:x">'});
  const landing=await fetch(h.base+"/board");assert.equal(landing.status,200);assert.match(await landing.text(),/method="post"/);
  const response=await fetch(h.base+"/board",{method:"POST",headers:{"content-type":"application/x-www-form-urlencoded"},body:new URLSearchParams({workspaceId:h.w.workspace.id,token:h.at})});
  const html=await response.text();assert.equal(response.status,200);
  assert.match(html,/&lt;Team &amp; Workspace&gt;/);assert.match(html,/&lt;script&gt;/);assert.match(html,/&lt;Alice &amp; Co&gt;/);
  assert.doesNotMatch(html,/<script|<img|javascript:/);assert.equal(html.includes(h.at),false);
  assert.equal(response.headers.get("content-type"),"text/html; charset=utf-8");assert.equal(response.headers.get("cache-control"),"no-store");
  assert.match(response.headers.get("content-security-policy")!,/default-src 'none'/);
  assert.equal((await fetch(h.base+`/board?workspaceId=${h.w.workspace.id}`,{headers:{authorization:`Bearer ${h.ot}`}})).status,200);
  assert.equal((await fetch(h.base+`/board?workspaceId=${h.w.workspace.id}`)).status,401);
  assert.equal((await fetch(h.base+"/board",{method:"POST",headers:{"content-type":"application/x-www-form-urlencoded"},body:new URLSearchParams({workspaceId:h.w.workspace.id,token:"bad"})})).status,401);
  assert.equal((await fetch(h.base+`/board?workspaceId=${h.w.workspace.id}&workspaceId=other`,{headers:{authorization:`Bearer ${h.ot}`}})).status,400);
  assert.equal((await fetch(h.base+"/board",{method:"POST",headers:{"content-type":"application/x-www-form-urlencoded"},body:`workspaceId=${h.w.workspace.id}&token=${h.at}&token=duplicate`})).status,400);
  await h.req(`${h.p}/members/${h.alice.id}`,"DELETE",h.ot);
  assert.equal((await fetch(h.base+"/board",{method:"POST",headers:{"content-type":"application/x-www-form-urlencoded"},body:new URLSearchParams({workspaceId:h.w.workspace.id,token:h.at})})).status,403);
  assert.equal(JSON.stringify(h.logs).includes(h.at),false);
});

test("recent board metadata is limited to latest 50 and task idempotency failure is fully atomic",async t=>{
  const h=await harness(t);
  h.store.db.exec("CREATE TRIGGER idem_fail BEFORE INSERT ON idempotency BEGIN SELECT RAISE(ABORT,'injected'); END");
  assert.equal((await h.declare("Must roll back",[],h.at,{}, {"idempotency-key":"fault"})).status,500);
  for(const table of ["task","idempotency"])assert.equal(h.store.db.prepare(`SELECT count(*) AS n FROM ${table}`).get()?.n,0);
  for(const table of ["document","document_version","change"])assert.equal(h.store.db.prepare(`SELECT count(*) AS n FROM ${table}`).get()?.n,1,"rollback retains only the initial index");
  assert.equal(h.store.db.prepare("SELECT seq FROM workspace_seq WHERE workspace_id=?").get(h.w.workspace.id)?.seq,h.initialSeq);
  h.store.db.exec("DROP TRIGGER idem_fail");
  for(let i=0;i<51;i++)assert.equal((await h.declare(`Task ${i}`)).status,201);
  const board=(await h.req(`${h.p}/board`,"GET",h.at)).body;
  assert.equal(board.recentChanges.length,50);assert.equal(board.recentChanges[0].seq,h.initialSeq+51);assert.equal(board.recentChanges.at(-1).seq,h.initialSeq+2);
  assert.equal(board.tasks.open.length,51);
});

test("presence failure cannot leave a committed mutation behind a failed HTTP response",async t=>{
  const h=await harness(t), tokens=h.store.db.prepare("SELECT count(*) AS n FROM workspace_token").get()?.n;
  h.store.db.exec("CREATE TRIGGER presence_fail BEFORE INSERT ON presence BEGIN SELECT RAISE(ABORT,'injected'); END");
  assert.equal((await h.declare("Presence rollback")).status,500);
  assert.equal(h.store.db.prepare("SELECT count(*) AS n FROM task").get()?.n,0);
  assert.equal(h.store.db.prepare("SELECT count(*) AS n FROM change").get()?.n,1,"only the initial index survives");
  assert.equal((await h.req("/api/connect","POST",h.as,{key:h.w.taskKey})).status,500);
  assert.equal(h.store.db.prepare("SELECT count(*) AS n FROM workspace_token").get()?.n,tokens);
});

test("v2 migration preserves historical rows and database enforces holder/status constraints",()=>{
  const db=new DatabaseSync(":memory:");
  try {
    db.exec("PRAGMA foreign_keys=ON");
    for(const migration of MIGRATIONS.filter(m=>m.version<=2))migration.apply(db);
    db.exec(`INSERT INTO schema_meta VALUES(1,2);INSERT INTO org VALUES('org','Org','now');
      INSERT INTO account(id,org_id,email,created_at) VALUES('acc','org','x@example.test','now');
      INSERT INTO workspace(id,org_id,name,slug,created_by,created_at) VALUES('ws','org','W','w','acc','now');
      INSERT INTO membership(workspace_id,account_id,role,status,created_at) VALUES('ws','acc','owner','active',0);
      INSERT INTO session_token(token_hash,account_id,created_at,expires_at) VALUES('retained-session-hash','acc',0,1000);
      INSERT INTO task_key(id,workspace_id,secret_hash,created_at) VALUES('key','ws','retained-key-hash',0);
      INSERT INTO document VALUES('doc','ws','specs/a','specs','acc',1,'hash','now','acc',NULL);
      INSERT INTO document_version VALUES('doc',1,'retained','hash','acc','now');`);
    applyMigrations(db);applyMigrations(db);
    assert.equal(db.prepare("SELECT version FROM schema_meta").get()?.version,CURRENT_SCHEMA_VERSION);
    assert.equal(db.prepare("SELECT content FROM document_version").get()?.content,"retained");
    assert.equal(db.prepare("SELECT token_hash FROM session_token").get()?.token_hash,"retained-session-hash");
    assert.equal(db.prepare("SELECT secret_hash FROM task_key").get()?.secret_hash,"retained-key-hash");
    const insert=db.prepare("INSERT INTO task (id,workspace_id,title,scope_json,status,declared_by,claimed_by,created_at,updated_at) VALUES (?,'ws','Task','[]',?,'acc',?,0,0)");
    assert.throws(()=>insert.run("bad","claimed",null),/CHECK/);
    assert.throws(()=>insert.run("bad","open","acc"),/CHECK/);
    assert.throws(()=>insert.run("bad","abandoned",null),/CHECK/);
    assert.throws(()=>insert.run("bad","claimed","unknown_member"),/FOREIGN KEY/);
  } finally {db.close();}
});

test("separate WAL connections observe exclusive claim, stale actors rejected and reopen persists history",async t=>{
  const dir=await mkdtemp(join(tmpdir(),"team-task-wal-")), path=join(dir,"db.sqlite");
  t.after(()=>rm(dir,{recursive:true,force:true}));
  const one=openTeamDatabase(path);
  const account=await createAccount(one,{orgId:"org",email:"one@example.test",displayName:"One",password:"connection test password"});
  const workspace=createWorkspace(one,account,{name:"Test",repos:[{url:"https://example.test/a.git",branch:"main"}]},0).workspace;
  assert.equal(workspace.seq,1); // Initial index plus two task versions after claim.
  const auth={workspaceId:workspace.id,account,role:"owner" as const};
  const task=declareTask(one,auth,{title:"Concurrent"},0).task;
  const two=openTeamDatabase(path);
  try {
    assert.equal(claimTask(two,auth,task.id,1).claimedBy,account.id);
    assert.throws(()=>claimTask(one,auth,task.id,2),(error:unknown)=>{assert.equal((error as {status:number}).status,409);return true;});
    two.db.prepare("UPDATE account SET disabled_at='disabled' WHERE id=?").run(account.id);
    assert.throws(()=>updateTask(one,auth,task.id,{status:"done"},3),(error:unknown)=>{assert.equal((error as {status:number}).status,403);return true;});
  } finally {two.close();one.close();}
  const reopened=openTeamDatabase(path);
  try {assert.equal(reopened.db.prepare("SELECT status FROM task WHERE id=?").get(task.id)?.status,"claimed");assert.equal(reopened.db.prepare("SELECT count(*) AS n FROM document_version").get()?.n,3);}
  finally {reopened.close();}
});
