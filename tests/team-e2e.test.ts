import assert from "node:assert/strict";
import test from "node:test";
import { mkdtemp, mkdir, realpath, readFile, writeFile, readdir, stat, rm, symlink, lstat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { execFile, execFileSync } from "node:child_process";
import { promisify } from "node:util";
import type { AddressInfo } from "node:net";
import type { Server } from "node:http";
import { openTeamDatabase } from "../server/store/sqlite.ts";
import { createAccount } from "../server/domain/identity.ts";
import { createTeamServer } from "../server/http/router.ts";
import { connectDirectory, loadCredentials } from "../runtime/opencode/plugins/vibe-v2/team/binding.ts";
import { TeamMirror } from "../runtime/opencode/plugins/vibe-v2/team/mirror.ts";
import { workspaceTools } from "../runtime/opencode/plugins/vibe-v2/team/tools.ts";
import { hashContent } from "../runtime/core/team/manifest.ts";
import type { HostContext, ToolDefinition } from "../runtime/opencode/plugins/vibe-v2/host-contract.ts";

async function fixture(t:{after(fn:()=>Promise<void>):void},count=2) {
  const base=await realpath(await mkdtemp(join(tmpdir(),"team-e2e-"))),dbPath=join(base,"team.sqlite"),password="e2e fixture password";
  let store=openTeamDatabase(dbPath),server:Server|undefined,port=0;
  const orgId="org_e2e",logs:{method:string;route:string;status:number}[]=[];
  const accounts=[];
  for(let i=0;i<count;i++)accounts.push(await createAccount(store,{orgId,email:`person${i}@example.test`,displayName:`Person ${i}`,password}));
  const start=async()=>{
    server=createTeamServer(store,{orgId,logger:entry=>logs.push(entry)});
    await new Promise<void>((r,j)=>{server!.once("error",j);server!.listen(port,"127.0.0.1",r);});port=(server.address() as AddressInfo).port;
  };
  const stop=async()=>{if(server){const active=server;server=undefined;active.closeAllConnections();await new Promise<void>((r,j)=>active.close(e=>e?j(e):r()));store.close();}};
  t.after(async()=>{await stop();await rm(base,{recursive:true,force:true});});await start();
  const serverUrl=`http://127.0.0.1:${port}`;
  const req=async(path:string,method="GET",token?:string,body?:unknown,headers:Record<string,string>={})=>{
    const response=await fetch(serverUrl+path,{method,headers:{...(token?{authorization:`Bearer ${token}`} : {}),...(body===undefined?{}:{"content-type":"application/json"}),...headers},...(body===undefined?{}:{body:JSON.stringify(body)})});
    return {status:response.status,body:await response.json() as any};
  };
  const sessions:string[]=[];
  for(const account of accounts){const login=await req("/api/auth/login","POST",undefined,{email:account.email,password});assert.equal(login.status,200);sessions.push(login.body.sessionToken);}
  const created=await req("/api/workspaces","POST",sessions[0],{name:"E2E workspace",repos:[{url:"https://example.test/team.git",branch:"main"}]});
  assert.equal(created.status,201);const w=created.body,p=`/api/workspaces/${w.workspace.id}`;
  const connected=await req("/api/connect","POST",sessions[0],{key:w.taskKey});assert.equal(connected.status,200);const ownerToken=connected.body.workspaceToken;
  for(let i=1;i<count;i++){
    if(i%2){assert.equal((await req(`${p}/invitations`,"POST",ownerToken,{email:accounts[i].email})).status,201);assert.equal((await req(`${p}/invitations/accept`,"POST",sessions[i],{})).status,200);}
    else {assert.equal((await req(`${p}/requests`,"POST",sessions[i],{})).status,201);assert.equal((await req(`${p}/members/${accounts[i].id}/decide`,"POST",ownerToken,{approve:true})).status,200);}
  }
  const clients=[];
  for(let i=0;i<count;i++){
    const root=join(base,`client${i}`),code=join(root,"code");await mkdir(code,{recursive:true,mode:0o700});
    execFileSync("git",["init","-b","main",code],{stdio:"ignore",windowsHide:true});execFileSync("git",["-C",code,"remote","add","origin","https://example.test/team.git"],{windowsHide:true});
    await connectDirectory(root,{serverUrl,sessionToken:sessions[i],key:w.taskKey});
    const credentials=await loadCredentials(root),mirror=new TeamMirror(root),tools=workspaceTools(root,mirror,async session=>session==="primary");
    const call=async(name:string,input:Record<string,unknown>={})=>JSON.parse((await tools.find(tool=>tool.name===name)!.execute(input,{sessionID:"primary",agent:"vibe-main"})).content);
    clients.push({root,mirror,credentials,call});
  }
  const manifest=async(i:number)=>JSON.parse(await readFile(join(clients[i].root,".vibe/.sync/manifest.json"),"utf8"));
  const sync=async(i:number)=>{const result=await clients[i].mirror.sync(true);assert.equal(result.ok,true,JSON.stringify(result));return result;};
  return {base,dbPath,serverUrl,accounts,sessions,w,p,ownerToken,clients,logs,req,manifest,sync,store:()=>store,stop,
    restart:async()=>{store=openTeamDatabase(dbPath);await start();}};
}

test("BR7 initialization is authoritative and materializes five layers for independent clients",async t=>{
  const h=await fixture(t),index=await h.req(`${h.p}/documents/index.json`,"GET",h.ownerToken);
  assert.equal(index.status,200);assert.equal(h.w.workspace.seq,1);
  const expected={schemaVersion:1,workspaceId:h.w.workspace.id,layers:["constitution","specs","work","members","activity"]};
  assert.deepEqual(JSON.parse(index.body.content),expected);assert.equal(index.body.version,1);
  for(let i=0;i<2;i++){
    // Existing files are not empty-directory placeholders to overwrite.
    await mkdir(join(h.clients[i].root,".vibe/activity"),{recursive:true});
    await writeFile(join(h.clients[i].root,".vibe/activity/user-copy.md"),"retain existing bytes");
    await h.sync(i);for(const layer of expected.layers)assert.equal((await stat(join(h.clients[i].root,".vibe",layer))).isDirectory(),true);
    assert.equal(await readFile(join(h.clients[i].root,".vibe/activity/user-copy.md"),"utf8"),"retain existing bytes");
    assert.deepEqual(JSON.parse(await readFile(join(h.clients[i].root,".vibe/index.json"),"utf8")),expected);
    assert.equal((await h.manifest(i)).entries["index.json"].hash,hashContent(index.body.content));
  }
  assert.equal((await h.req(`${h.p}/documents/index.json`,"PUT",h.ownerToken,{content:"no"},{"if-match":"1"})).status,422);
});

test("layer initialization fails closed on file/symlink collisions and does not run after auth loss",async t=>{
  const h=await fixture(t),client=h.clients[1];
  await writeFile(join(client.root,".vibe/specs"),"not a directory");
  assert.equal((await client.mirror.sync(true)).ok,false);
  assert.equal(await readFile(join(client.root,".vibe/specs"),"utf8"),"not a directory");assert.equal((await h.manifest(1)).cursor,0);
  await rm(join(client.root,".vibe/specs"));const outside=join(h.base,"outside");await mkdir(outside);
  await symlink(outside,join(client.root,".vibe/specs"));
  assert.equal((await client.mirror.sync(true)).ok,false);assert.equal((await lstat(join(client.root,".vibe/specs"))).isSymbolicLink(),true);
  assert.deepEqual(await readdir(outside),[]);assert.equal((await h.manifest(1)).cursor,0);
  await rm(join(client.root,".vibe/specs"));
  assert.equal((await h.req(`${h.p}/members/${h.accounts[1].id}`,"DELETE",h.ownerToken)).status,200);
  const result=await client.mirror.sync(true);assert.equal(result.lastError,"authentication_required");
  await assert.rejects(()=>stat(join(client.root,".vibe/specs")),/ENOENT/);
});

test("Q1/Q3 two real clients converge versions, preserve denied shared edits and unmanaged copies",async t=>{
  const h=await fixture(t);await h.sync(0);await h.sync(1);
  const owner=h.clients[0],member=h.clients[1],path=`members/${h.accounts[0].id}/progress.md`;
  assert.equal((await owner.call("workspace_record_progress",{kind:"progress",text:"owner progress"})).status,"synced");
  await h.sync(1);const remote=(await h.req(`${h.p}/documents/${path}`,"GET",h.ownerToken)).body;
  assert.equal((await h.manifest(1)).entries[path].version,remote.version);assert.equal(await readFile(join(member.root,".vibe",path),"utf8"),remote.content);
  await mkdir(join(owner.root,".vibe/specs/modules"),{recursive:true});await writeFile(join(owner.root,".vibe/specs/modules/auth.md"),"approved auth");
  await writeFile(join(owner.root,"AGENTS.md"),"owner constitution");await h.sync(0);await h.sync(1);
  assert.equal(await readFile(join(member.root,"AGENTS.md"),"utf8"),"owner constitution");
  const before=(await h.req(`${h.p}/documents/specs/modules/auth.md`,"GET",h.ownerToken)).body;
  await writeFile(join(member.root,".vibe/specs/modules/auth.md"),"unsaved member edit");
  await mkdir(join(member.root,".vibe copy"));await writeFile(join(member.root,".vibe copy","my-notes.md"),"untouched user copy");
  const sync=await h.sync(1);assert.ok(sync.warnings.some(w=>w.includes("请联系负责人")));
  const after=(await h.req(`${h.p}/documents/specs/modules/auth.md`,"GET",h.ownerToken)).body;
  assert.equal(after.version,before.version);assert.equal(after.content,"approved auth");
  assert.equal(await readFile(join(member.root,".vibe/specs/modules/auth.md"),"utf8"),"approved auth");
  const copies=(await readdir(join(member.root,".vibe/specs/modules"))).filter(name=>name.includes(".conflict-"));
  assert.equal(await readFile(join(member.root,".vibe/specs/modules",copies[0]),"utf8"),"unsaved member edit");
  assert.equal(await readFile(join(member.root,".vibe copy/my-notes.md"),"utf8"),"untouched user copy");
  await rm(join(owner.root,".vibe/specs/modules/auth.md"));await h.sync(0);await h.sync(1);
  await assert.rejects(()=>stat(join(member.root,".vibe/specs/modules/auth.md")),/ENOENT/);
  assert.equal(await readFile(join(member.root,".vibe/specs/modules",copies[0]),"utf8"),"unsaved member edit");
});

test("Q2 ten real identities write independent progress concurrently without409 and converge",{timeout:30000},async t=>{
  const h=await fixture(t,10);await Promise.all(h.clients.map((_,i)=>h.sync(i)));
  const results=await Promise.all(h.clients.map((client,i)=>client.call("workspace_record_progress",{kind:"progress",text:`parallel writer ${i}`})));
  for(const result of results)assert.equal(result.status,"synced",JSON.stringify(result));
  await Promise.all(h.clients.map((_,i)=>h.sync(i)));
  assert.equal(h.logs.filter(log=>log.route==="documents.put").length,10);
  assert.equal(h.logs.some(log=>log.status===409),false);
  const head=(await h.req(h.p,"GET",h.ownerToken)).body.workspace.seq;
  for(let i=0;i<10;i++){
    const manifest=await h.manifest(i);assert.equal(manifest.cursor,head);
    for(let j=0;j<10;j++){
      const path=`members/${h.accounts[j].id}/progress.md`,doc=(await h.req(`${h.p}/documents/${path}`,"GET",h.ownerToken)).body;
      assert.equal(manifest.entries[path].version,doc.version);assert.equal(manifest.entries[path].hash,doc.hash);
      assert.equal(await readFile(join(h.clients[i].root,".vibe",path),"utf8"),doc.content);
    }
  }
  assert.equal(h.store().db.prepare("SELECT count(*) AS n FROM document WHERE layer='members'").get()?.n,10);
});

test("real task tools/board/removal agree and removed credentials preserve local bytes",async t=>{
  const h=await fixture(t);await h.sync(0);await h.sync(1);const owner=h.clients[0],member=h.clients[1];
  const declared=await member.call("workspace_task_declare",{title:"Auth",scope:["src/auth/"]}),id=declared.task.id;
  const overlap=await owner.call("workspace_task_declare",{title:"Login",scope:["src/auth/login.ts"]});assert.equal(overlap.overlapWarnings[0].taskId,id);
  assert.equal((await owner.call("workspace_task_claim",{id})).task.claimedBy,h.accounts[0].id);
  assert.equal((await member.call("workspace_task_claim",{id})).claimedBy,h.accounts[0].id);
  assert.equal((await owner.call("workspace_task_update",{id,status:"abandoned",reason:"handoff"})).task.status,"abandoned");
  await member.call("workspace_task_claim",{id});await member.call("workspace_task_update",{id,status:"done"});
  await member.call("workspace_task_claim",{id:overlap.task.id});await h.sync(0);await h.sync(1);
  const work=JSON.parse(await readFile(join(owner.root,`.vibe/work/${id}.json`),"utf8"));assert.equal(work.status,"done");
  assert.equal((await h.req(`${h.p}/board`,"GET",h.ownerToken)).body.tasks.done[0].claimedBy,h.accounts[1].id);
  const progress=`.vibe/members/${h.accounts[1].id}/progress.md`;await mkdir(join(member.root,progress,".."),{recursive:true});await writeFile(join(member.root,progress),"pending before removal");
  assert.equal((await h.req(`${h.p}/members/${h.accounts[1].id}`,"DELETE",h.ownerToken)).status,200);
  const removed=await member.mirror.sync(true);assert.equal(removed.ok,false);assert.equal(removed.lastError,"authentication_required");
  assert.equal(await readFile(join(member.root,progress),"utf8"),"pending before removal");await h.sync(0);
  const board=(await h.req(`${h.p}/board`,"GET",h.ownerToken)).body;
  assert.ok(board.tasks.open.some((task:any)=>task.id===overlap.task.id));assert.equal(board.members.length,1);
  assert.equal(JSON.parse(await readFile(join(owner.root,`.vibe/work/${overlap.task.id}.json`),"utf8")).status,"open");
});

test("offline local progress survives real server/database restart and reconnect keys remain scoped",async t=>{
  const h=await fixture(t);await h.sync(0);await h.sync(1);const client=h.clients[1];
  const cursor=(await h.manifest(1)).cursor;await h.stop();
  const saved=await client.call("workspace_record_progress",{kind:"progress",text:"saved during real outage"});assert.equal(saved.status,"saved_locally");
  assert.equal((await h.manifest(1)).cursor,cursor);await h.restart();
  await h.sync(1);await h.sync(0);const path=`members/${h.accounts[1].id}/progress.md`;
  assert.match((await h.req(`${h.p}/documents/${path}`,"GET",h.ownerToken)).body.content,/saved during real outage/);
  const rotated=await h.req(`${h.p}/keys/rotate`,"POST",h.ownerToken,{});assert.equal(rotated.status,200);
  await assert.rejects(()=>connectDirectory(client.root,{serverUrl:h.serverUrl,sessionToken:h.sessions[1],key:h.w.taskKey}),/authentication_required/);
  await h.sync(1); // Already-issued workspace credential has its own TTL.
  const old=client.credentials.workspaceToken;
  await connectDirectory(client.root,{serverUrl:h.serverUrl,sessionToken:h.sessions[1],key:rotated.body.taskKey});
  assert.notEqual((await loadCredentials(client.root)).workspaceToken,old);await h.sync(1);
});

test("real pagination checkpoints a contiguous prefix and converges beyond200 changes",{timeout:30000},async t=>{
  const h=await fixture(t);for(let i=0;i<205;i++)assert.equal((await h.req(`${h.p}/documents/specs/page/${i}.md`,"PUT",h.ownerToken,{content:`page ${i}`},{"if-match":"0"})).status,200);
  const first=(await h.req(`${h.p}/changes?since=0&limit=200`,"GET",h.ownerToken)).body;assert.equal(first.hasMore,true);assert.equal(first.nextSeq,200);
  assert.deepEqual(first.changes.map((change:any)=>change.seq),Array.from({length:200},(_,i)=>i+1));
  const head=(await h.req(h.p,"GET",h.ownerToken)).body.workspace.seq;assert.equal(head,206);
  const last=(await h.req(`${h.p}/changes?since=200&limit=200`,"GET",h.ownerToken)).body;
  assert.equal(last.hasMore,false);assert.equal(last.nextSeq,head);assert.deepEqual(last.changes.map((change:any)=>change.seq),[201,202,203,204,205,206]);
  let previous=0;
  for(let round=0;round<8&&previous<head;round++){
    const result=await h.clients[1].mirror.sync(true),manifest=await h.manifest(1);
    if(!result.ok)assert.equal(result.lastError,"budget_exhausted",JSON.stringify(result));
    assert.ok(manifest.cursor>=previous);previous=manifest.cursor;
  }
  assert.equal(previous,head);
  const manifest=await h.manifest(1);assert.equal(Object.keys(manifest.entries).length,206);
  for(let i=0;i<205;i++){
    const path=`specs/page/${i}.md`,doc=(await h.req(`${h.p}/documents/${path}`,"GET",h.ownerToken)).body;
    assert.equal(manifest.entries[path].hash,doc.hash);assert.equal(manifest.entries[path].version,doc.version);
    assert.equal(await readFile(join(h.clients[1].root,".vibe",path),"utf8"),`page ${i}`);
  }
});

test("index initialization failure rolls back the complete workspace creation transaction",async t=>{
  const h=await fixture(t),tables=["workspace","workspace_repo","membership","task_key","document","document_version","workspace_seq","change"];
  const counts=()=>tables.map(table=>h.store().db.prepare(`SELECT count(*) AS n FROM ${table}`).get()?.n),before=counts();
  h.store().db.exec("CREATE TRIGGER fail_index BEFORE INSERT ON change WHEN NEW.path='index.json' BEGIN SELECT RAISE(ABORT,'injected'); END");
  const created=await h.req("/api/workspaces","POST",h.sessions[0],{name:"Rollback",repos:[{url:"https://example.test/rollback.git",branch:"main"}]});
  assert.equal(created.status,500);assert.deepEqual(counts(),before);
  assert.equal((await h.req(h.p,"GET",h.ownerToken)).body.workspace.seq,h.w.workspace.seq);
});

test("installed connector binds a directory without Git and syncs via the real server",{timeout:30000},async t=>{
  const h=await fixture(t),profile=join(h.base,"profile");await mkdir(profile);
  const original={model:"fixture-model",custom:{retain:true},permissions:[{action:"shell",resource:"*",effect:"ask"}]};
  await writeFile(join(profile,"opencode.json"),JSON.stringify(original),{mode:0o600});
  const exec=promisify(execFile);
  await exec("python3",["scripts/vibe_v2_installer.py","install","--opencode-home",profile],{timeout:10000,windowsHide:true});
  await exec("python3",["scripts/vibe_v2_installer.py","verify","--opencode-home",profile],{timeout:10000,windowsHide:true});
  const config=JSON.parse(await readFile(join(profile,"opencode.json"),"utf8"));for(const key of Object.keys(original))assert.deepEqual(config[key],original[key as keyof typeof original]);
  await assert.rejects(()=>stat(join(profile,"server")),/ENOENT/);
  const modulePath=(name:string)=>pathToFileURL(join(profile,"runtime/opencode/plugins/vibe-v2",name)).href;
  const root=join(h.base,"installed-client");await mkdir(root);
  const cli=await exec(process.execPath,["--experimental-strip-types",join(profile,"runtime/opencode/plugins/vibe-v2/team/connect.ts"),root],{
    env:{...process.env,TEAM_SERVER_URL:h.serverUrl,TEAM_SESSION_TOKEN:h.sessions[1],TEAM_TASK_KEY:h.w.taskKey},timeout:10000,windowsHide:true});assert.match(cli.stdout,/Connected/);
  const {TeamMirror:InstalledMirror}=await import(modulePath("team/mirror.ts"));const mirror=new InstalledMirror(root);assert.equal((await mirror.sync()).ok,true);
  const result=await mirror.recordProgress("progress","from installed modules");assert.equal(result.status,"synced");await h.sync(0);
  assert.match(await readFile(join(h.clients[0].root,`.vibe/members/${h.accounts[1].id}/progress.md`),"utf8"),/from installed modules/);
  const {setup}=await import(modulePath("setup.ts")),tools=new Map<string,ToolDefinition>(),hooks:any[]=[];
  const ctx:HostContext={location:{directory:root},storage:{get:async()=>undefined,set:async()=>{},remove:async()=>{}},
    command:{transform:async f=>f({add:()=>{}})},tool:{transform:async f=>f({add:t=>{tools.set(t.name,t);}}),hook:async()=>{}},permission:{hook:async()=>{}},
    session:{get:async()=>({directory:root,agent:"vibe-main"}),context:async()=>[],prompt:async()=>{},hook:async(_,f)=>{hooks.push(f);}}};
  await setup(ctx);assert.equal(tools.size,10);const event={sessionID:"installed",system:[] as {type:"text";text:string}[]};for(const hook of hooks)await hook(event);
  assert.ok(event.system.some(part=>part.text.includes("Team workspace")));assert.equal(JSON.parse((await tools.get("workspace_status")!.execute({}, {sessionID:"installed",agent:"vibe-main"})).content).lastError,null);
});
