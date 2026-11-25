import assert from "node:assert/strict";
import test from "node:test";
import type { AddressInfo } from "node:net";
import { DatabaseSync } from "node:sqlite";
import { openTeamDatabase, applyMigrations } from "../server/store/sqlite.ts";
import { MIGRATIONS, CURRENT_SCHEMA_VERSION } from "../server/store/schema.ts";
import { createAccount, login as loginAccount, hashToken, SESSION_TTL_MS, WORKSPACE_TTL_MS } from "../server/domain/identity.ts";
import { createTeamServer } from "../server/http/router.ts";

const PASSWORD = "test-only password 012345";
async function harness(t: {after(fn: () => Promise<void>): void}) {
  const store = openTeamDatabase(":memory:");
  let now = Date.parse("2026-11-23T10:00:00.000Z");
  const orgId = "org_test";
  const owner = await createAccount(store,{orgId,email:"owner@example.test",displayName:"Owner",password:PASSWORD});
  const alice = await createAccount(store,{orgId,email:"alice@example.test",displayName:"Alice",password:PASSWORD});
  const bob = await createAccount(store,{orgId,email:"bob@example.test",displayName:"Bob",password:PASSWORD});
  const logs: unknown[] = [];
  const server = createTeamServer(store,{orgId,now:()=>now,logger:entry=>logs.push(entry)});
  await new Promise<void>(resolve=>server.listen(0,"127.0.0.1",resolve));
  const base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  t.after(async()=>{ await new Promise<void>((resolve,reject)=>server.close(error=>error?reject(error):resolve())); store.close(); });
  const req = async (path: string, method="GET", token?: string, body?: unknown, headers: Record<string,string>={}) => {
    const response = await fetch(base+path,{method,headers:{...(token?{authorization:`Bearer ${token}`} : {}),...(body===undefined?{}:{"content-type":"application/json"}),...headers},...(body===undefined?{}:{body:JSON.stringify(body)})});
    return {status:response.status,body:await response.json() as any,headers:response.headers};
  };
  const login = async(email="owner@example.test") => {
    const result = await req("/api/auth/login","POST",undefined,{email,password:PASSWORD});
    assert.equal(result.status,200,JSON.stringify(result.body)); return result.body.sessionToken as string;
  };
  const connect = async(token:string,key:string) => req("/api/connect","POST",token,{key});
  const workspace = async(sessionToken:string,name="Workspace") => {
    const created = await req("/api/workspaces","POST",sessionToken,{name,repos:[{url:"https://example.test/team.git",branch:"main"}]});
    assert.equal(created.status,201,JSON.stringify(created.body));
    const initialSeq=1; // New workspaces contain exactly the server-managed index event.
    assert.equal(created.body.workspace.seq,initialSeq);
    const connected = await connect(sessionToken,created.body.taskKey);
    assert.equal(connected.status,200,JSON.stringify(connected.body));
    const baseline=await req(`/api/workspaces/${created.body.workspace.id}/changes?since=0`,"GET",connected.body.workspaceToken);
    assert.equal(baseline.status,200);assert.equal(baseline.body.changes.length,1);
    assert.equal(baseline.body.changes[0].path,"index.json");assert.equal(baseline.body.changes[0].seq,initialSeq);
    return {id:created.body.workspace.id as string,key:created.body.taskKey as string,token:connected.body.workspaceToken as string,initialSeq};
  };
  return {store,server,base,orgId,owner,alice,bob,logs,req,login,connect,workspace,advance:(ms:number)=>{now+=ms;},now:()=>now};
}

test("schema upgrades add identity data without changing existing document history", () => {
  const db = new DatabaseSync(":memory:");
  try {
    MIGRATIONS[0].apply(db);
    db.exec(`INSERT INTO schema_meta VALUES (1,1); INSERT INTO org VALUES ('org','Test','now');
      INSERT INTO workspace (id,org_id,name,slug,created_by,created_at) VALUES ('ws','org','Test','test','acc','now');
      INSERT INTO document VALUES ('doc','ws','specs/a.md','specs','acc',1,'abc','now','acc',NULL);
      INSERT INTO document_version VALUES ('doc',1,'retained','abc','acc','now');`);
    applyMigrations(db); applyMigrations(db);
    assert.equal(db.prepare("SELECT version FROM schema_meta").get()?.version,CURRENT_SCHEMA_VERSION);
    assert.equal(db.prepare("SELECT content FROM document_version").get()?.content,"retained");
    for (const table of ["session_token","workspace_token","workspace_repo","membership","invitation","task_key","idempotency"]) {
      assert.ok(db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name=?").get(table),table);
    }
  } finally {db.close();}
});

test("v4 keeps existing session tokens and allows permanent ones", () => {
  const db = new DatabaseSync(":memory:");
  try {
    MIGRATIONS[0].apply(db); MIGRATIONS[1].apply(db);
    db.exec(`INSERT INTO schema_meta VALUES (1,2); INSERT INTO org VALUES ('org','Test','now');
      INSERT INTO account (id,org_id,email,password_hash,display_name,created_at) VALUES ('acc','org','a@example.test','h','A','now');
      INSERT INTO session_token (token_hash,account_id,created_at,expires_at) VALUES ('legacyhash','acc',100,200);`);
    applyMigrations(db);
    const migrated = db.prepare("SELECT * FROM session_token").get() as any;
    assert.equal(migrated.token_hash,"legacyhash");
    assert.equal(migrated.name,"Login token");
    assert.equal(migrated.expires_at,200);
    assert.equal(migrated.last_used_at,null);
    db.exec(`INSERT INTO session_token (id,token_hash,account_id,name,created_at,expires_at) VALUES ('tok_p','perm','acc','Permanent',300,NULL)`);
    assert.equal((db.prepare("SELECT expires_at FROM session_token WHERE id='tok_p'").get() as any).expires_at,null);
    assert.throws(()=>db.exec(`INSERT INTO session_token (id,token_hash,account_id,name,created_at,expires_at) VALUES ('tok_x','x','acc','Bad',300,200)`));
  } finally {db.close();}
});

test("HTTP login/workspace/connect scopes credentials and persists hashes only", async t => {
  const h = await harness(t), session = await h.login();
  assert.equal((await h.req("/api/workspaces")).status,401);
  assert.equal((await h.req("/api/auth/login","POST",undefined,{email:"owner@example.test",password:"bad password"})).status,401);
  const w = await h.workspace(session);
  assert.equal((await h.connect(session,w.key)).body.accountId,h.owner.id);
  assert.equal((await h.req("/api/connect","POST",undefined,{key:w.key},{authorization:session})).status,401);
  assert.equal((await h.req(`/api/workspaces/${w.id}`,"GET",session)).status,401);
  const meta = await h.req(`/api/workspaces/${w.id}`,"GET",w.token);
  assert.equal(meta.status,200); assert.equal(meta.body.workspace.orgId,h.orgId);
  assert.equal(meta.body.workspace.ownerAccountId,h.owner.id);
  assert.equal(JSON.stringify(meta.body).includes(w.key),false);
  assert.equal((await h.req("/api/workspaces","GET",session)).body.workspaces.length,1);
  assert.equal((await h.req("/api/workspaces","GET",w.token)).status,401);
  assert.ok(h.store.db.prepare("SELECT token_hash FROM session_token WHERE token_hash=?").get(hashToken(session)));
  assert.ok(h.store.db.prepare("SELECT token_hash FROM workspace_token WHERE token_hash=?").get(hashToken(w.token)));
  assert.ok(h.store.db.prepare("SELECT secret_hash FROM task_key WHERE secret_hash=?").get(hashToken(w.key)));
  assert.equal(meta.headers.get("cache-control"),"no-store");
});

test("invitation requires matching-account acceptance; applications require owner approval", async t => {
  const h = await harness(t), os = await h.login(), as = await h.login("alice@example.test"), bs = await h.login("bob@example.test");
  const w = await h.workspace(os), path = `/api/workspaces/${w.id}`;
  assert.equal((await h.connect(as,w.key)).status,403);
  assert.equal((await h.req(`${path}/changes?since=0`,"GET",as)).status,401);
  assert.equal((await h.req(`${path}/invitations`,"POST",w.token,{email:"alice@example.test"})).status,201);
  assert.equal((await h.connect(as,w.key)).status,403);
  assert.equal((await h.req(`${path}/invitations/accept`,"POST",bs,{})).status,404);
  assert.equal((await h.req(`${path}/invitations/accept`,"POST",as,{})).status,200);
  const ac = await h.connect(as,w.key); assert.equal(ac.status,200); assert.equal(ac.body.role,"member");
  assert.equal((await h.req(`${path}/requests`,"POST",bs,{})).status,201);
  assert.equal((await h.connect(bs,w.key)).status,403);
  assert.equal((await h.req(`${path}/members/${h.bob.id}/decide`,"POST",ac.body.workspaceToken,{approve:true})).status,403);
  assert.equal((await h.req(`${path}/members/${h.bob.id}/decide`,"POST",w.token,{approve:false})).status,200);
  assert.equal((await h.connect(bs,w.key)).status,403);
  assert.equal((await h.req(`${path}/requests`,"POST",bs,{})).status,201);
  assert.equal((await h.req(`${path}/members/${h.bob.id}/decide`,"POST",w.token,{approve:true})).status,200);
  assert.equal((await h.connect(bs,w.key)).status,200);
  const members = await h.req(`${path}/members`,"GET",w.token);
  assert.equal(members.status,200); assert.equal(members.body.members.filter((m:any)=>m.status==="active").length,3);
});

test("rotation/expiry and member removal block new connects and revoke old workspace access", async t => {
  const h=await harness(t), os=await h.login(), as=await h.login("alice@example.test"), w=await h.workspace(os), p=`/api/workspaces/${w.id}`;
  await h.req(`${p}/invitations`,"POST",w.token,{email:"alice@example.test"});
  await h.req(`${p}/invitations/accept`,"POST",as,{});
  const ac=(await h.connect(as,w.key)).body.workspaceToken;
  assert.equal((await h.req(`${p}/keys/rotate`,"POST",ac,{})).status,403);
  const rotated=await h.req(`${p}/keys/rotate`,"POST",w.token,{expiresAt:new Date(h.now()+1000).toISOString()});
  assert.equal(rotated.status,200); assert.notEqual(rotated.body.taskKey,w.key);
  assert.equal((await h.connect(os,w.key)).status,401);
  assert.equal((await h.req(p,"GET",ac)).status,200); // Keys gate connects, not existing member identity.
  h.advance(1000); assert.equal((await h.connect(os,rotated.body.taskKey)).status,401);
  const next=await h.req(`${p}/keys/rotate`,"POST",w.token,{});
  assert.equal((await h.req(`${p}/members/${h.owner.id}`,"DELETE",w.token)).status,409);
  assert.equal((await h.req(`${p}/members/${h.alice.id}`,"DELETE",w.token)).status,200);
  assert.equal((await h.req(p,"GET",ac)).status,403);
  assert.equal((await h.connect(as,next.body.taskKey)).status,403);
  await h.req(`${p}/invitations`,"POST",w.token,{email:"alice@example.test"});
  await h.req(`${p}/invitations/accept`,"POST",as,{});
  assert.equal((await h.connect(as,next.body.taskKey)).status,200);
  assert.notEqual((await h.req(p,"GET",ac)).status,200); // Rejoin must not revive old credentials.
});

test("documents enforce current namespace/owner permissions and If-Match without leaking content", async t => {
  const h=await harness(t), os=await h.login(), as=await h.login("alice@example.test"), w=await h.workspace(os), p=`/api/workspaces/${w.id}`;
  await h.req(`${p}/invitations`,"POST",w.token,{email:"alice@example.test"}); await h.req(`${p}/invitations/accept`,"POST",as,{});
  const ac=(await h.connect(as,w.key)).body.workspaceToken;
  const doc=`${p}/documents/specs/a.md`, first=await h.req(doc,"PUT",w.token,{content:"PRIVATE SERVER CONTENT"},{"if-match":"0"});
  assert.equal(first.status,200); assert.equal(first.body.version,1);
  assert.equal((await h.req(doc,"GET",ac)).body.content,"PRIVATE SERVER CONTENT");
  assert.equal((await h.req(doc,"PUT",ac,{content:"unauthorized"},{"if-match":"1"})).status,403);
  const conflict=await h.req(doc,"PUT",w.token,{content:"stale"},{"if-match":"0"});
  assert.equal(conflict.status,409); assert.equal(conflict.body.error.details.currentVersion,1);
  assert.equal(JSON.stringify(conflict.body).includes("PRIVATE SERVER CONTENT"),false);
  assert.equal((await h.req(doc,"PUT",w.token,{content:"missing match"})).status,400);
  const own=`${p}/documents/members/${h.alice.id}/progress.md`;
  assert.equal((await h.req(own,"PUT",ac,{content:"progress",accountId:h.bob.id},{"if-match":"0"})).status,200);
  assert.equal((await h.req(`${p}/documents/members/${h.bob.id}/x.md`,"PUT",ac,{content:"no"},{"if-match":"0"})).status,403);
  for (const path of ["work/t.json","activity/a.json","index.json"]) assert.equal((await h.req(`${p}/documents/${path}`,"PUT",w.token,{content:"no"},{"if-match":"0"})).status,422);
  assert.equal((await h.req(doc,"DELETE",w.token,undefined,{"if-match":"1"})).status,200);
  assert.equal((await h.req(doc+"?version=1","GET",ac)).body.content,"PRIVATE SERVER CONTENT");
  const changes=await h.req(`${p}/changes?since=${w.initialSeq}&limit=2`,"GET",ac);
  assert.equal(changes.status,200); assert.equal(changes.body.hasMore,true);
  assert.deepEqual(changes.body.changes.map((c:any)=>c.seq),[w.initialSeq+1,w.initialSeq+2]);
  assert.equal((await h.req(`${p}/changes?since=${w.initialSeq+2}`,"GET",ac)).body.changes[0].op,"delete");
  assert.equal(JSON.stringify(h.logs).includes("PRIVATE SERVER CONTENT"),false);
  for (const secret of [os,as,w.key,w.token,ac,PASSWORD]) assert.equal(JSON.stringify(h.logs).includes(secret),false);
});

test("credential scope, disabled accounts, TTL boundaries, unknown membership and org isolation", async t => {
  const h=await harness(t), login=await h.login();
  const longLived=await h.req("/api/tokens","POST",login,{name:"Test session",expiresIn:"forever"});
  const session=longLived.body.secret as string;
  const w=await h.workspace(session), other=await h.workspace(session,"Other");
  assert.equal((await h.req(`/api/workspaces/${other.id}/changes?since=0`,"GET",w.token)).status,403);
  await createAccount(h.store,{orgId:"org_other",email:"outsider@example.test",displayName:"Outside",password:PASSWORD});
  assert.equal((await h.req("/api/auth/login","POST",undefined,{email:"outsider@example.test",password:PASSWORD})).status,401);
  h.advance(WORKSPACE_TTL_MS); assert.equal((await h.req(`/api/workspaces/${w.id}`,"GET",w.token)).status,401);
  const reconnected=await h.connect(session,w.key); assert.equal(reconnected.status,200);
  h.store.db.prepare("UPDATE account SET disabled_at='disabled' WHERE id=?").run(h.owner.id);
  assert.equal((await h.req(`/api/workspaces/${w.id}`,"GET",reconnected.body.workspaceToken)).status,401);
  h.store.db.prepare("UPDATE account SET disabled_at=NULL WHERE id=?").run(h.owner.id);
  // A finite identity token still expires; revoked membership stops reconnecting.
  const shortLived=await h.req("/api/tokens","POST",session,{name:"Short",expiresIn:"day"});
  assert.equal((await h.req("/api/workspaces","GET",shortLived.body.secret)).status,200);
  h.advance(24*60*60*1000+1);
  assert.equal((await h.req("/api/workspaces","GET",shortLived.body.secret)).status,401);
  assert.equal((await h.req("/api/workspaces","GET",session)).status,200);
});

test("identity tokens are self-managed: create with lifetime, list, extend and revoke", async t => {
  const h=await harness(t), session=await h.login();
  const list=await h.req("/api/tokens","GET",session);
  assert.equal(list.status,200);
  assert.equal(list.body.tokens.length,1);
  assert.equal(list.body.tokens[0].current,true);
  assert.equal(list.body.tokens[0].name,"Login token");
  assert.equal(list.body.tokens[0].lastUsedAt!==null,true);
  assert.equal(JSON.stringify(list.body).includes(session),false,"plaintext must never be listed");

  const day=await h.req("/api/tokens","POST",session,{name:"Server script",expiresIn:"day"});
  assert.equal(day.status,201); assert.match(day.body.secret,/^[A-Za-z0-9_-]{43}$/u);
  const week=await h.req("/api/tokens","POST",session,{name:"Laptop",expiresIn:"week"});
  const month=await h.req("/api/tokens","POST",session,{name:"Tablet",expiresIn:"month"});
  const forever=await h.req("/api/tokens","POST",session,{name:"Desktop",expiresIn:"forever"});
  assert.equal(forever.status,201); assert.equal(forever.body.token.expiresAt,null);
  assert.equal((await h.req("/api/tokens","POST",session,{name:"Bad",expiresIn:"year"})).status,422);
  assert.equal((await h.req("/api/tokens","POST",session,{name:"",expiresIn:"day"})).status,422);

  // A created token is a working credential, not a display record.
  assert.equal((await h.req("/api/workspaces","GET",day.body.secret)).status,200);
  assert.equal((await h.req("/api/workspaces","GET",forever.body.secret)).status,200);
  assert.equal(month.status,201);

  const after=await h.req("/api/tokens","GET",session);
  assert.equal(after.body.tokens.length,5);
  assert.equal(after.body.tokens.filter((x:any)=>x.current).length,1);
  for(const token of after.body.tokens) assert.equal(typeof token.createdAt,"string");

  // A day token expires on its own; permanent tokens do not.
  h.advance(24*60*60*1000+1);
  assert.equal((await h.req("/api/workspaces","GET",day.body.secret)).status,401);
  assert.equal((await h.req("/api/workspaces","GET",forever.body.secret)).status,200);

  // Extend only moves forward and skips permanent tokens.
  const weekId=week.body.token.id;
  const extended=await h.req(`/api/tokens/${weekId}/extend`,"POST",session,{expiresIn:"week"});
  assert.equal(extended.status,200);
  assert.ok(Date.parse(extended.body.token.expiresAt)>Date.parse(week.body.token.expiresAt));
  assert.equal((await h.req(`/api/tokens/${forever.body.token.id}/extend`,"POST",session,{expiresIn:"week"})).status,422);

  // Revocation is immediate and idempotent-safe; other accounts cannot touch it.
  assert.equal((await h.req(`/api/tokens/${weekId}`,"DELETE",session)).status,200);
  assert.equal((await h.req("/api/workspaces","GET",week.body.secret)).status,401);
  assert.equal((await h.req(`/api/tokens/${weekId}`,"DELETE",session)).status,404);
  assert.equal((await h.req(`/api/tokens/${weekId}/extend`,"POST",session,{expiresIn:"day"})).status,404);
  const other=await h.login("alice@example.test");
  assert.equal((await h.req(`/api/tokens/${forever.body.token.id}`,"DELETE",other)).status,404);
  const aliceList=await h.req("/api/tokens","GET",other);
  assert.equal(aliceList.body.tokens.every((x:any)=>x.name!=="Desktop"),true);
  // Revoking the credential in use is allowed and takes effect on the next request.
  assert.equal((await h.req("/api/tokens","GET",other)).status,200);
  const selfId=aliceList.body.tokens[0].id;
  assert.equal((await h.req(`/api/tokens/${selfId}`,"DELETE",other)).status,200);
  assert.equal((await h.req("/api/tokens","GET",other)).status,401);
});

test("workspace-bound idempotency is atomic, account scoped and never stores plaintext keys", async t => {
  const h=await harness(t), session=await h.login(), w=await h.workspace(session), p=`/api/workspaces/${w.id}`;
  const headers={"idempotency-key":"doc-once","if-match":"0"}, doc=`${p}/documents/specs/once.md`;
  const first=await h.req(doc,"PUT",w.token,{content:"once"},headers);
  assert.equal(first.status,200); assert.deepEqual(await h.req(doc,"PUT",w.token,{content:"once"},headers).then(r=>r.body),first.body);
  assert.equal((await h.req(doc,"PUT",w.token,{content:"different"},headers)).status,409);
  assert.equal(h.store.db.prepare("SELECT count(*) AS n FROM change WHERE workspace_id=?").get(w.id)?.n,w.initialSeq+1);
  const rotated=await h.req(`${p}/keys/rotate`,"POST",w.token,{}, {"idempotency-key":"rotate-once"});
  assert.equal(rotated.status,200);
  assert.equal((await h.req(`${p}/keys/rotate`,"POST",w.token,{}, {"idempotency-key":"rotate-once"})).status,409);
  assert.equal((await h.connect(session,rotated.body.taskKey)).status,200);
  const rows=JSON.stringify(h.store.db.prepare("SELECT * FROM idempotency").all());
  assert.equal(rows.includes(rotated.body.taskKey),false); assert.equal(rows.includes(w.token),false);
  assert.equal((await h.req("/api/workspaces","POST",session,{name:"No replay",repos:[]},{"idempotency-key":"unsupported"})).status,422);
});

test("HTTP input bounds, path rejection and login throttling fail closed", async t => {
  const h=await harness(t), s=await h.login(), w=await h.workspace(s), p=`/api/workspaces/${w.id}`;
  assert.equal((await h.req("/api/workspaces","POST",s,{name:"No repos",repos:[]})).status,422);
  assert.equal((await h.req(`${p}/documents/specs/%2E%2E%2Fescape.md`,"PUT",w.token,{content:"no"},{"if-match":"0"})).status,422);
  assert.equal((await h.req(`${p}/documents/specs/a%5Cb.md`,"PUT",w.token,{content:"no"},{"if-match":"0"})).status,422);
  assert.equal((await h.req(`${p}/documents/specs/large.md`,"PUT",w.token,{content:"x".repeat(1024*1024+1)},{"if-match":"0"})).status,413);
  assert.equal((await h.req(`${p}/documents/specs/huge.md`,"PUT",w.token,{content:"x".repeat(2*1024*1024+1)},{"if-match":"0"})).status,413);
  assert.equal((await h.req(`${p}/changes?since=-1`,"GET",w.token)).status,422);
  assert.equal((await h.req(`${p}/changes?since=0&limit=501`,"GET",w.token)).status,422);
  assert.equal((await h.req(`${p}/changes?since=0&since=1`,"GET",w.token)).status,400);
  for(let i=0;i<5;i++) assert.equal((await h.req("/api/auth/login","POST",undefined,{email:"nobody@example.test",password:PASSWORD})).status,401);
  assert.equal((await h.req("/api/auth/login","POST",undefined,{email:"nobody@example.test",password:PASSWORD})).status,429);
  h.advance(15*60*1000); assert.equal((await h.req("/api/auth/login","POST",undefined,{email:"nobody@example.test",password:PASSWORD})).status,401);
});

test("invitation to a not-yet-provisioned account, role injection, and current token revocation", async t => {
  const h=await harness(t), os=await h.login(), w=await h.workspace(os), p=`/api/workspaces/${w.id}`;
  assert.equal((await h.req(`${p}/invitations`,"POST",w.token,{email:"future@example.test",role:"owner"})).status,422);
  assert.equal((await h.req(`${p}/invitations`,"POST",w.token,{email:"future@example.test"})).status,201);
  const future=await createAccount(h.store,{orgId:h.orgId,email:"future@example.test",displayName:"Future",password:PASSWORD});
  const fs=await h.login("future@example.test");
  const acceptHeaders={"idempotency-key":"accept-once"};
  assert.equal((await h.req(`${p}/invitations/accept`,"POST",fs,{},acceptHeaders)).status,200);
  assert.equal((await h.req(`${p}/invitations/accept`,"POST",fs,{},acceptHeaders)).status,200);
  const fc=await h.connect(fs,w.key); assert.equal(fc.status,200); assert.equal(fc.body.role,"member");
  assert.equal((await h.req(`${p}/members/${h.owner.id}/decide`,"POST",fc.body.workspaceToken,{approve:true,role:"owner"})).status,403);
  h.store.db.prepare("UPDATE session_token SET revoked_at=? WHERE token_hash=?").run(h.now(),hashToken(fs));
  assert.equal((await h.connect(fs,w.key)).status,401);
  assert.equal((await h.req(p,"GET",fc.body.workspaceToken)).status,200);
  h.store.db.prepare("UPDATE workspace_token SET revoked_at=? WHERE token_hash=?").run(h.now(),hashToken(fc.body.workspaceToken));
  assert.equal((await h.req(p,"GET",fc.body.workspaceToken)).status,401);
  assert.equal(h.store.db.prepare("SELECT status FROM membership WHERE account_id=?").get(future.id)?.status,"active");
});

test("idempotency failure rolls back nested document writes and cannot replay across accounts", async t => {
  const h=await harness(t), os=await h.login(), w=await h.workspace(os), p=`/api/workspaces/${w.id}`;
  const headers={"idempotency-key":"atomic","if-match":"0"}, doc=`${p}/documents/specs/a.md`;
  h.store.db.exec(`CREATE TRIGGER fail_idempotency BEFORE INSERT ON idempotency BEGIN SELECT RAISE(ABORT,'injected'); END`);
  assert.equal((await h.req(doc,"PUT",w.token,{content:"atomic"},headers)).status,500);
  for(const table of ["document","document_version","change"]) {
    assert.equal(h.store.db.prepare(`SELECT count(*) AS n FROM ${table}`).get()?.n,1,"only the initial index survives rollback");
  }
  assert.equal(h.store.db.prepare("SELECT count(*) AS n FROM idempotency").get()?.n,0);
  assert.equal(h.store.db.prepare("SELECT seq FROM workspace_seq WHERE workspace_id=?").get(w.id)?.seq,w.initialSeq);
  h.store.db.exec("DROP TRIGGER fail_idempotency");
  assert.equal((await h.req(doc,"PUT",w.token,{content:"atomic"},headers)).body.version,1);
  await h.req(`${p}/invitations`,"POST",w.token,{email:"alice@example.test"}); const as=await h.login("alice@example.test");
  await h.req(`${p}/invitations/accept`,"POST",as,{}); const ac=(await h.connect(as,w.key)).body.workspaceToken;
  assert.equal((await h.req(`${p}/documents/members/${h.alice.id}/x.md`,"PUT",ac,{content:"atomic"},headers)).status,409);
  assert.equal(h.store.db.prepare("SELECT count(*) AS n FROM document").get()?.n,2);
  const changed=await h.req(`${p}/keys/rotate`,"POST",w.token,{}, {"idempotency-key":"rotate-expiry"});
  h.advance(24*60*60*1000);
  const again=await h.req(`${p}/keys/rotate`,"POST",w.token,{}, {"idempotency-key":"rotate-expiry"});
  assert.equal(again.status,200); assert.notEqual(again.body.taskKey,changed.body.taskKey);
});

test("invalid JSON/UTF-8 and malformed queries do not mutate state or leak errors", async t => {
  const h=await harness(t), os=await h.login(), w=await h.workspace(os), p=`/api/workspaces/${w.id}`;
  for(const body of ["{",Buffer.from([0x7b,0x22,0x78,0x22,0x3a,0x22,0xff,0x22,0x7d])]) {
    const response=await fetch(h.base+`${p}/documents/specs/a.md`,{method:"PUT",headers:{authorization:`Bearer ${w.token}`,"if-match":"0","content-type":"application/json"},body});
    assert.equal(response.status,400); assert.equal((await response.json() as any).error.code,"invalid_request");
  }
  assert.equal((await h.req(`${p}/documents/specs/%`,"GET",w.token)).status,400);
  assert.equal((await h.req(`${p}/documents/specs/a.md?version=0`,"GET",w.token)).status,422);
  assert.equal((await h.req(`${p}/keys/rotate`,"POST",w.token,{expiresAt:"not a timestamp"})).status,422);
  assert.equal((await h.req(`${p}/keys/rotate`,"POST",w.token,{expiresAt:new Date(h.now()).toISOString()})).status,422);
  assert.equal((await h.req(`${p}/changes?since=${w.initialSeq+1}`,"GET",w.token)).status,422);
  assert.equal((await h.req("/api/metrics")).status,401);
  assert.equal((await h.req("/api/metrics","GET",os)).status,200);
  assert.equal((await h.req("/api/healthz")).body.schemaVersion,CURRENT_SCHEMA_VERSION);
  assert.equal(h.store.db.prepare("SELECT count(*) AS n FROM document").get()?.n,1,"invalid requests leave only the initial index");
});

test("an account disabled during asynchronous password verification cannot receive a session", async t => {
  const h=await harness(t);
  const pending=loginAccount(h.store,h.orgId,{email:"owner@example.test",password:PASSWORD},h.now());
  h.store.db.prepare("UPDATE account SET disabled_at='disabled' WHERE id=?").run(h.owner.id);
  await assert.rejects(pending,(error:unknown)=>{assert.equal((error as {status:number}).status,401);return true;});
  assert.equal(h.store.db.prepare("SELECT count(*) AS n FROM session_token").get()?.n,0);
});

test("concurrent login failures cannot all pass the five-attempt admission boundary", async t => {
  const h=await harness(t);
  const results=await Promise.all(Array.from({length:6},()=>h.req("/api/auth/login","POST",undefined,{email:"owner@example.test",password:"wrong concurrent password"})));
  assert.deepEqual(results.map(r=>r.status).sort(),[401,401,401,401,401,429]);
  assert.equal((await h.req("/api/auth/login","POST",undefined,{email:"owner@example.test",password:PASSWORD})).status,429);
});
