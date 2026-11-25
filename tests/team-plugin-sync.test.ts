import assert from "node:assert/strict";
import test from "node:test";
import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import { mkdtemp, readFile, writeFile, mkdir, readdir, rm, stat, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { execFileSync, execFile } from "node:child_process";
import { promisify } from "node:util";
import { setup } from "../runtime/opencode/plugins/vibe-v2/setup.ts";
import type { HostContext, ToolDefinition, JsonValue } from "../runtime/opencode/plugins/vibe-v2/host-contract.ts";
import { teamContext } from "../runtime/opencode/plugins/vibe-v2/team/context.ts";
import { TeamClient } from "../runtime/opencode/plugins/vibe-v2/team/client.ts";
import { hashContent } from "../runtime/core/team/manifest.ts";
import { connectDirectory, loadCredentials } from "../runtime/opencode/plugins/vibe-v2/team/binding.ts";
import { shouldEnableTeamModules } from "../runtime/opencode/plugins/vibe-v2/team/gate.ts";
import { TeamMirror } from "../runtime/opencode/plugins/vibe-v2/team/mirror.ts";
import { SafeFiles, withProjectLock } from "../runtime/opencode/plugins/vibe-v2/team/files.ts";

async function fixture(t:{after(fn:()=>Promise<void>):void}) {
  const root=await mkdtemp(join(tmpdir(),"team-mirror-"));
  const token="a".repeat(43), documents=new Map<string,any>(), changes:any[]=[], calls:{method:string;path:string;body:any}[]=[];
  const meta={id:"ws_test",ownerAccountId:"owner",name:"Test team",repos:[{url:"https://example.test/repo.git",branch:"main"}]};
  let accountId="alice", denied=0, slow=false, malformed=false;
  const put=(path:string,content:string|null)=>{
    const version=(documents.get(path)?.version??0)+1,hash=content===null?null:hashContent(content);
    const doc={path,version,hash,content};documents.set(path,doc);
    changes.push({seq:changes.length+1,path,op:content===null?"delete":"upsert",version,...(hash===null?{}:{hash}),content});return doc;
  };
  const server=createServer(async(req,res)=>{
    const buffers=[];for await(const part of req)buffers.push(part);const text=Buffer.concat(buffers).toString();
    const body=text?JSON.parse(text):{},url=new URL(req.url!,"http://local");calls.push({method:req.method!,path:url.pathname,body});
    if(slow){setTimeout(()=>{if(!res.destroyed){res.writeHead(503);res.end("{}");}},150);return;}
    if(denied){res.writeHead(denied);res.end("{}");return;}
    const reply=(status:number,value:unknown)=>{res.writeHead(status,{"content-type":"application/json"});res.end(JSON.stringify(value));};
    if(url.pathname==="/api/connect")return reply(200,{workspaceToken:token,accountId,workspace:meta,role:"member"});
    if(req.headers.authorization!==`Bearer ${token}`)return reply(401,{});
    if(url.pathname==="/api/workspaces/ws_test")return reply(200,{workspace:meta,role:"member"});
    if(url.pathname.endsWith("/changes")) {
      const since=Number(url.searchParams.get("since")), batch=changes.filter(c=>c.seq>since).slice(0,200);
      return reply(200,{changes:malformed?[{...batch[0],seq:since+2}]:batch,hasMore:false,cursor:batch.at(-1)?.seq??since});
    }
    if(url.pathname.endsWith("/tasks"))return reply(201,{task:{id:"task_test",title:body.title}});
    if(url.pathname.endsWith("/tasks/task_test/claim"))return reply(409,{error:{message:token,details:{claimedBy:"owner",status:"claimed"}}});
    const prefix="/api/workspaces/ws_test/documents/";
    if(url.pathname.startsWith(prefix)) {
      const path=decodeURIComponent(url.pathname.slice(prefix.length)),current=documents.get(path);
      if(req.method==="GET")return reply(current?200:404,current??{});
      const expected=Number(req.headers["if-match"]);
      if(expected!==(current?.version??0))return reply(409,{error:{details:{currentVersion:current?.version??0,currentHash:current?.hash??null}}});
      const doc=put(path,req.method==="DELETE"?null:body.content);return reply(200,{version:doc.version,hash:doc.hash,seq:changes.length});
    }
    return reply(404,{});
  });
  await new Promise<void>(resolve=>server.listen(0,"127.0.0.1",resolve));
  const serverUrl=`http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  t.after(async()=>{server.closeAllConnections();await new Promise<void>(resolve=>server.close(()=>resolve()));await rm(root,{recursive:true,force:true});});
  const input={serverUrl,sessionToken:"s".repeat(43),key:"k".repeat(32)};
  const connect=()=>connectDirectory(root,input);
  const local=async(path:string,content:string)=>{await mkdir(join(root,path,".."),{recursive:true});await writeFile(join(root,path),content);};
  const manifest=async()=>JSON.parse(await readFile(join(root,".vibe/.sync/manifest.json"),"utf8"));
  return {root,serverUrl,token,meta,documents,changes,calls,put,connect,input,local,manifest,setAccount:(id:string)=>{accountId=id;},
    denied:(value:number)=>{denied=value;},slow:(value:boolean)=>{slow=value;},malformed:(value:boolean)=>{malformed=value;}};
}

test("gate stays off until explicit successful connect; credentials are private and binding immutable",async t=>{
  const h=await fixture(t);assert.equal(await shouldEnableTeamModules(h.root),false);
  h.denied(401);await assert.rejects(h.connect,/authentication_required/);assert.equal(await shouldEnableTeamModules(h.root),false);
  h.denied(0);
  await h.connect();assert.equal(await shouldEnableTeamModules(h.root),true);
  const creds=await loadCredentials(h.root);assert.equal(creds.accountId,"alice");assert.equal(creds.workspaceToken,h.token);
  assert.equal((await stat(join(h.root,".vibe/.sync/credentials.json"))).mode&0o777,0o600);
  h.meta.id="ws_other";await assert.rejects(h.connect,/bound/);
  h.meta.id="ws_test";h.setAccount("bob");await assert.rejects(h.connect,/already bound to another account/);
  await assert.rejects(()=>connectDirectory(h.root,{...h.input,serverUrl:"http://127.0.0.1:1"}),/already bound to another server/);
  assert.deepEqual(await loadCredentials(h.root),creds);
});

test("mirror pulls baseline preserving existing bytes; then pushes only authorized changes",async t=>{
  const h=await fixture(t);h.put("specs/a.md","authority");h.put("members/alice/progress.md","old");
  await h.local(".vibe/specs/a.md","unsaved before connect");await h.connect();const mirror=new TeamMirror(h.root);
  assert.equal((await mirror.sync()).ok,true);assert.equal(await readFile(join(h.root,".vibe/specs/a.md"),"utf8"),"authority");
  const copies=(await readdir(join(h.root,".vibe/specs"))).filter(name=>name.includes(".conflict-"));assert.equal(copies.length,1);
  assert.equal(await readFile(join(h.root,".vibe/specs",copies[0]),"utf8"),"unsaved before connect");
  await h.local(".vibe/members/alice/progress.md","my progress");await h.local(".vibe/specs/a.md","forbidden edit");
  const result=await mirror.sync();assert.equal(result.ok,true);assert.ok(result.warnings.some(w=>w.includes("请联系负责人")));
  assert.equal(h.documents.get("members/alice/progress.md").content,"my progress");assert.equal(h.documents.get("specs/a.md").content,"authority");
  assert.equal(await readFile(join(h.root,".vibe/specs/a.md"),"utf8"),"authority");
  assert.equal(h.calls.filter(c=>c.method==="PUT"&&c.path.endsWith("specs/a.md")).length,0);
});

test("409 conflict preserves local bytes without retry; equal hash acknowledges response loss",async t=>{
  const h=await fixture(t);h.put("members/alice/progress.md","one");await h.connect();const mirror=new TeamMirror(h.root);await mirror.sync();
  await h.local(".vibe/members/alice/progress.md","local");h.put("members/alice/progress.md","remote");
  await mirror.sync();assert.equal(h.calls.filter(c=>c.method==="PUT").length,1);
  assert.equal(await readFile(join(h.root,".vibe/members/alice/progress.md"),"utf8"),"remote");
  const files=await readdir(join(h.root,".vibe/members/alice"));assert.equal(files.some(f=>f.includes(".conflict-")),true);
  await h.local(".vibe/members/alice/progress.md","response lost");const remote=h.put("members/alice/progress.md","response lost");
  await mirror.sync();assert.equal((await h.manifest()).entries["members/alice/progress.md"].version,remote.version);
  assert.equal((await readdir(join(h.root,".vibe/members/alice"))).filter(f=>f.includes(".conflict-")).length,1);
});

test("deletes affect tracked unchanged reversible paths only; stale replay cannot resurrect acknowledged deletion",async t=>{
  const h=await fixture(t);h.put("members/alice/progress.md","v1");h.put("specs/a.md","spec");
  await h.connect();const mirror=new TeamMirror(h.root);await mirror.sync();
  await h.local(".vibe/specs/copy.conflict-20261123T100000Z-123abc","my copy");
  await rm(join(h.root,".vibe/members/alice/progress.md"));await mirror.sync();
  assert.equal(h.documents.get("members/alice/progress.md").content,null);
  h.put("specs/a.md",null);await mirror.sync();await assert.rejects(()=>stat(join(h.root,".vibe/specs/a.md")),/ENOENT/);
  assert.equal(await readFile(join(h.root,".vibe/specs/copy.conflict-20261123T100000Z-123abc"),"utf8"),"my copy");
  const manifest=await h.manifest();manifest.cursor=0;await writeFile(join(h.root,".vibe/.sync/manifest.json"),JSON.stringify(manifest));
  await new TeamMirror(h.root).sync();await assert.rejects(()=>stat(join(h.root,".vibe/members/alice/progress.md")),/ENOENT/);
});

test("gapped/malformed batches and corrupt manifests do not overwrite files or cursor",async t=>{
  const h=await fixture(t);h.put("specs/a.md","remote");await h.connect();await h.local(".vibe/specs/a.md","local");h.malformed(true);
  const mirror=new TeamMirror(h.root);assert.equal((await mirror.sync()).ok,false);assert.equal((await h.manifest()).cursor,0);
  assert.equal(await readFile(join(h.root,".vibe/specs/a.md"),"utf8"),"local");assert.equal(h.calls.filter(c=>c.path.endsWith("/changes")).length,2);
  await writeFile(join(h.root,".vibe/.sync/manifest.json"),"broken");const before=h.calls.length;
  assert.equal((await mirror.sync(true)).ok,false);assert.equal(h.calls.length,before);
  await rm(join(h.root,".vibe/.sync/manifest.json"));assert.equal((await mirror.sync(true)).ok,false);assert.equal(h.calls.length,before);
});

test("HTTP timeout aborts without detached writes; backoff and auth loss preserve local state",async t=>{
  const h=await fixture(t);await h.connect();let clock=0;const mirror=new TeamMirror(h.root,{budgetMs:80,now:()=>clock});
  h.slow(true);const start=Date.now();assert.equal((await mirror.sync()).ok,false);assert.ok(Date.now()-start<300);
  const before=h.calls.length;assert.equal((await mirror.sync()).ok,false);assert.equal(h.calls.length,before);
  h.slow(false);clock=15000;assert.equal((await mirror.sync()).ok,true);
  h.denied(401);assert.equal((await mirror.sync(true)).ok,false);const deniedCalls=h.calls.length;
  clock+=120000;await mirror.sync();assert.equal(h.calls.length,deniedCalls);
});

test("filesystem guards reject symlinks and case collisions; lock prevents concurrent writers",async t=>{
  const h=await fixture(t);await h.connect();const files=new SafeFiles(h.root);
  await mkdir(join(h.root,"outside"));await symlink(join(h.root,"outside"),join(h.root,".vibe/specs"));
  await assert.rejects(()=>files.write(".vibe/specs/a.md","no"),/symlink|collision/);assert.deepEqual(await readdir(join(h.root,"outside")),[]);
  await rm(join(h.root,".vibe/specs"));await h.local(".vibe/specs/A.md","original");
  await assert.rejects(()=>files.write(".vibe/specs/a.md","overwrite"),/case|collision/);
  await assert.rejects(()=>files.write("../escape","no"),/path/);
  await assert.rejects(()=>files.write(".vibe/specs/A.md","stale replace",hashContent("older")),/local_changed/);
  await assert.rejects(()=>files.remove(".vibe/specs/A.md",hashContent("older")),/local_changed/);
  await withProjectLock(h.root,async()=>{await assert.rejects(()=>withProjectLock(h.root,async()=>{}),/busy/);});
  assert.equal(await readFile(join(h.root,".vibe/specs/A.md"),"utf8"),"original");
});

test("maximum-length UTF-8 basenames pull and preserve local bytes on replacement",async t=>{
  const h=await fixture(t),names=["a".repeat(214),"b".repeat(215),"c".repeat(255),"界".repeat(85)];
  for(const name of names){assert.ok(Buffer.byteLength(name)<=255);h.put(`specs/${name}`,`initial-${Buffer.byteLength(name)}`);}
  await h.connect();const mirror=new TeamMirror(h.root);
  assert.equal((await mirror.sync()).ok,true,"initial pull must support all legal basename lengths");
  const originals:Buffer[]=[];
  for(const name of names) {
    const relative=`.vibe/specs/${name}`;
    assert.equal(await readFile(join(h.root,relative),"utf8"),`initial-${Buffer.byteLength(name)}`);
    const original=Buffer.from([0xff,0x00,...Buffer.from(`unsaved-${name}`)]);originals.push(original);
    await writeFile(join(h.root,relative),original);h.put(`specs/${name}`,`replacement-${Buffer.byteLength(name)}`);
  }
  assert.equal((await mirror.sync()).ok,true,"replacement must preserve long-name local content");
  const siblings=await readdir(join(h.root,".vibe/specs")),copies=siblings.filter(name=>name.includes(".conflict-"));
  assert.equal(copies.length,names.length);assert.equal(siblings.some(name=>name.includes(".tmp-")),false);
  const saved=await Promise.all(copies.map(async name=>{assert.ok(Buffer.byteLength(name)<=255);assert.equal(name.includes("\uFFFD"),false);return readFile(join(h.root,".vibe/specs",name));}));
  for(const original of originals)assert.ok(saved.some(bytes=>bytes.equals(original)),"every original byte sequence survives");
  for(const name of names)assert.equal(await readFile(join(h.root,".vibe/specs",name),"utf8"),`replacement-${Buffer.byteLength(name)}`);
  assert.equal((await h.manifest()).cursor,h.changes.length);
});

test("progress writes reject editor saves after capture for existing and absent snapshots",async t=>{
  const h=await fixture(t);await h.connect();h.denied(503);
  const relative=".vibe/members/alice/progress.md";
  for(const mode of ["append-existing","append-absent","replace-existing"]) {
    await rm(join(h.root,relative),{force:true});
    if(mode!=="append-absent")await h.local(relative,"captured baseline");
    const mirror=new TeamMirror(h.root),write=mirror.files.write.bind(mirror.files),editor=Buffer.from(`editor save: ${mode}`);
    let injected=false;
    mirror.files.write=async(path,bytes,expected)=>{
      if(path===relative){injected=true;await h.local(relative,editor.toString());}
      return write(path,bytes,expected);
    };
    const calls=h.calls.length;
    await assert.rejects(()=>mirror.recordProgress("progress","tool update",mode.startsWith("append")?"append":"replace"),/local_changed/);
    assert.equal(injected,true);assert.deepEqual(await readFile(join(h.root,relative)),editor);
    assert.equal(h.calls.length,calls,"failed local save must not upload anything");
    assert.equal((await h.manifest()).cursor,0);
  }
});

test("stale dead-process locks recover under the acquisition guard, live or malformed locks fail closed",async t=>{
  const h=await fixture(t);await h.connect();const lock=join(h.root,".vibe/.sync/lock.json");
  await writeFile(lock,JSON.stringify({pid:2147483647,at:Date.now()-600001,nonce:"old"}));
  await withProjectLock(h.root,async()=>{});await assert.rejects(()=>stat(lock),/ENOENT/);
  await writeFile(lock,JSON.stringify({pid:process.pid,at:0,nonce:"live"}));await assert.rejects(()=>withProjectLock(h.root,async()=>{}),/busy/);
  await writeFile(lock,"broken");await assert.rejects(()=>withProjectLock(h.root,async()=>{}),/busy/);
  await rm(lock);await withProjectLock(h.root,async()=>{});
});

test("binds despite missing repositories, differing branches and extra repositories; child reuses memory root",async t=>{
  const h=await fixture(t);h.meta.repos.push({url:"https://example.test/missing.git",branch:"main"});
  const repo=(name:string,url:string,branch:string)=>{
    const dir=join(h.root,name);
    execFileSync("git",["init","-b",branch,dir],{stdio:"ignore",windowsHide:true});
    execFileSync("git",["-C",dir,"remote","add","origin",url],{windowsHide:true});
    return dir;
  };
  const dir=repo("code",h.meta.repos[0].url,"feature/work"),extra=repo("unrelated","https://example.test/extra.git","main");
  await h.connect();assert.equal(await shouldEnableTeamModules(h.root),true);
  const creds=await loadCredentials(h.root);
  assert.deepEqual(await connectDirectory(dir,h.input),{workspaceId:creds.workspaceId,accountId:creds.accountId,role:"member"});
  await assert.rejects(()=>stat(join(dir,".vibe")),/ENOENT/);
  await assert.rejects(()=>stat(join(extra,".vibe")),/ENOENT/);
  assert.equal(execFileSync("git",["-C",dir,"symbolic-ref","--short","HEAD"],{windowsHide:true}).toString().trim(),"feature/work");
});

test("the executable connector uses environment credentials without echoing or persisting account secrets",async t=>{
  const h=await fixture(t),sessionToken="s".repeat(43),key="k".repeat(32);
  const result=await promisify(execFile)(process.execPath,["--experimental-strip-types",resolve("runtime/opencode/plugins/vibe-v2/team/connect.ts"),h.root],{
    env:{...process.env,TEAM_SERVER_URL:h.serverUrl,TEAM_SESSION_TOKEN:sessionToken,TEAM_TASK_KEY:key},timeout:5000,windowsHide:true});
  assert.match(result.stdout,/Connected/);for(const secret of [sessionToken,key,h.token])assert.equal(result.stdout.includes(secret),false);
  const credentials=await readFile(join(h.root,".vibe/.sync/credentials.json"),"utf8");assert.equal(credentials.includes(sessionToken),false);assert.equal(credentials.includes(key),false);
  assert.equal(await shouldEnableTeamModules(h.root),true);
});

test("bound reconnect tool schema never accepts raw secrets; environment reauth returns only identity",async t=>{
  const h=await fixture(t);await h.connect();const bound=await host(h.root),tool=bound.tools.get("workspace_connect")!;
  assert.deepEqual(tool.input.properties,{});assert.equal(tool.input.additionalProperties,false);
  const oldSession=process.env.TEAM_SESSION_TOKEN,oldKey=process.env.TEAM_TASK_KEY;
  try {
    process.env.TEAM_SESSION_TOKEN="s".repeat(43);process.env.TEAM_TASK_KEY="k".repeat(32);
    const result=(await tool.execute({}, {sessionID:"main",agent:"vibe-main"})).content;
    assert.equal(JSON.parse(result).accountId,"alice");for(const secret of [process.env.TEAM_SESSION_TOKEN,process.env.TEAM_TASK_KEY,h.token])assert.equal(result.includes(secret),false);
  } finally {
    if(oldSession===undefined)delete process.env.TEAM_SESSION_TOKEN;else process.env.TEAM_SESSION_TOKEN=oldSession;
    if(oldKey===undefined)delete process.env.TEAM_TASK_KEY;else process.env.TEAM_TASK_KEY=oldKey;
  }
});

async function host(root:string) {
  const tools=new Map<string,ToolDefinition>(),hooks:((e:{sessionID:string;system:{type:"text";text:string}[]})=>Promise<void>)[]=[],records=new Map<string,JsonValue>();
  const ctx:HostContext={location:{directory:root},storage:{get:async k=>records.get(k),set:async(k,v)=>{records.set(k,v);},remove:async k=>{records.delete(k);}},
    command:{transform:async f=>f({add:()=>{}})},tool:{transform:async f=>f({add:d=>{tools.set(d.name,d);}}),hook:async()=>{}},permission:{hook:async()=>{}},
    session:{get:async({sessionID})=>({directory:root,...(sessionID==="review"?{parentID:"main",agent:"vibe-reviewer"}:{agent:"vibe-main"})}),context:async()=>[],prompt:async()=>{},hook:async(_,f)=>{hooks.push(f);}}};
  await setup(ctx);return {tools,hooks,ctx,context:async(sessionID="main")=>{const e={sessionID,system:[] as {type:"text";text:string}[]};for(const hook of hooks)await hook(e);return e.system;}};
}

test("existing setup keeps unbound registry identical and only bound primary matching Sessions synchronize",async t=>{
  const h=await fixture(t),unbound=await host(h.root);
  assert.deepEqual([...unbound.tools.keys()].sort(),["vibe_set_session_mode","vibe_task_control"]);assert.equal(unbound.hooks.length,1);
  assert.equal(h.calls.length,0);assert.deepEqual(await readdir(h.root),[]);
  h.put("specs/a.md","cached");await h.connect();const bound=await host(h.root);
  assert.equal(bound.tools.size,10);assert.equal(bound.hooks.length,2);
  const before=h.calls.length;await bound.context("review");assert.equal(h.calls.length,before);
  const system=await bound.context();assert.equal(system.length,2);assert.match(system[1].text,/Team workspace/);
  assert.equal(await readFile(join(h.root,".vibe/specs/a.md"),"utf8"),"cached");
  const tool=bound.tools.get("workspace_sync")!;assert.match((await tool.execute({}, {sessionID:"review",agent:"vibe-reviewer"})).content,/Rejected/);
  const outside=await mkdtemp(join(tmpdir(),"team-outside-"));t.after(()=>rm(outside,{recursive:true,force:true}));
  bound.ctx.session.get=async()=>({directory:outside,agent:"vibe-main"});const count=h.calls.length;
  await bound.context();assert.equal(h.calls.length,count);assert.match((await tool.execute({}, {sessionID:"main",agent:"vibe-main"})).content,/Rejected/);
});

test("progress survives offline; direct task tools do not queue and expose only holder metadata on conflicts",async t=>{
  const h=await fixture(t);await h.connect();const bound=await host(h.root);await bound.context();
  const call=async(name:string,input:Record<string,unknown>)=>JSON.parse((await bound.tools.get(name)!.execute(input,{sessionID:"main",agent:"vibe-main"})).content);
  h.denied(503);const progress=await call("workspace_record_progress",{kind:"progress",text:"saved offline"});
  assert.equal(progress.status,"saved_locally");assert.match(await readFile(join(h.root,".vibe/members/alice/progress.md"),"utf8"),/saved offline/);
  assert.equal((await call("workspace_status",{})).pending,1);
  h.denied(0);const declared=await call("workspace_task_declare",{title:"direct"});assert.equal(declared.task.id,"task_test");
  const conflict=await call("workspace_task_claim",{id:"task_test"});assert.equal(conflict.claimedBy,"owner");assert.equal(JSON.stringify(conflict).includes(h.token),false);
  assert.equal(h.calls.filter(c=>c.path.endsWith("/tasks/task_test/claim")).length,1);
  await call("workspace_sync",{});assert.equal(h.documents.get("members/alice/progress.md").content.includes("saved offline"),true);
});

test("unknown paths mirror under _unmapped without deletion and user copy artifacts are never pushed",async t=>{
  const h=await fixture(t);h.put("foreign/notes.md","unknown");await h.connect();const mirror=new TeamMirror(h.root);await mirror.sync();
  assert.equal(await readFile(join(h.root,".vibe/_unmapped/foreign/notes.md"),"utf8"),"unknown");
  await h.local(".vibe/members/alice/progress copy.md","private copied notes");await mkdir(join(h.root,".vibe copy"));
  h.put("foreign/notes.md",null);const result=await mirror.sync();assert.equal(result.ok,true);
  assert.equal(await readFile(join(h.root,".vibe/_unmapped/foreign/notes.md"),"utf8"),"unknown");
  assert.equal(h.calls.some(c=>c.method==="PUT"&&c.body.content==="private copied notes"),false);
  assert.equal(result.warnings.some(w=>w.includes("ignored copy")),true);
});

test("prototype-like unknown paths are mirrored and round-trip as own manifest keys",async t=>{
  const h=await fixture(t);h.put("constructor","constructor bytes");h.put("__proto__","prototype bytes");await h.connect();
  const result=await new TeamMirror(h.root).sync();assert.equal(result.ok,true);
  assert.equal(await readFile(join(h.root,".vibe/_unmapped/constructor"),"utf8"),"constructor bytes");
  assert.equal(await readFile(join(h.root,".vibe/_unmapped/__proto__"),"utf8"),"prototype bytes");
  const manifest=await h.manifest();assert.equal(Object.hasOwn(manifest.entries,"constructor"),true);assert.equal(Object.hasOwn(manifest.entries,"__proto__"),true);
});

test("a known newer pushed version is not overwritten by older stream events, owner edits and unauthorized deletes work",async t=>{
  const h=await fixture(t);h.meta.ownerAccountId="alice";h.put("specs/a.md","one");h.put("members/other/progress.md","other");
  await h.connect();const mirror=new TeamMirror(h.root);await mirror.sync();
  await h.local(".vibe/specs/a.md","owned edit");await rm(join(h.root,".vibe/members/other/progress.md"));
  await mirror.sync();assert.equal(h.documents.get("specs/a.md").content,"owned edit");assert.equal(await readFile(join(h.root,".vibe/members/other/progress.md"),"utf8"),"other");
  const manifest=await h.manifest();manifest.cursor=0;await writeFile(join(h.root,".vibe/.sync/manifest.json"),JSON.stringify(manifest));
  await new TeamMirror(h.root).sync();assert.equal(await readFile(join(h.root,".vibe/specs/a.md"),"utf8"),"owned edit");
  assert.equal((await h.manifest()).cursor,h.changes.length);
});

test("client rejects credential redirects and oversized responses and propagates caller abort",async t=>{
  let leaked=false;
  const target=createServer((req,res)=>{leaked=Boolean(req.headers.authorization);res.end("{}");});await new Promise<void>(r=>target.listen(0,"127.0.0.1",r));
  const source=createServer((req,res)=>{
    if(req.url!.includes("redirect")){res.writeHead(302,{location:`http://127.0.0.1:${(target.address() as AddressInfo).port}`});res.end();}
    else if(req.url!.includes("large"))res.end(JSON.stringify({content:"x".repeat(10*1024*1024)}));
    else{res.writeHead(401);res.end("not json");}
  });await new Promise<void>(r=>source.listen(0,"127.0.0.1",r));
  t.after(async()=>{source.closeAllConnections();target.closeAllConnections();await Promise.all([new Promise<void>(r=>source.close(()=>r())),new Promise<void>(r=>target.close(()=>r()))]);});
  const client=new TeamClient(`http://127.0.0.1:${(source.address() as AddressInfo).port}`,"a".repeat(43));
  await assert.rejects(()=>client.request("/redirect"),/network_unavailable/);assert.equal(leaked,false);
  await assert.rejects(()=>client.request("/large"),/response_too_large/);
  await assert.rejects(()=>client.request("/large","POST",{content:"x".repeat(2*1024*1024)}),/request_too_large/);
  await assert.rejects(()=>client.request("/auth"),(e:any)=>e.status===401);
  const abort=new AbortController();abort.abort();await assert.rejects(()=>client.request("/large","GET",undefined,{},Date.now()+1500,abort.signal),/budget_exhausted/);
});

test("invalid inline hashes fail before writing; manifest write failure is recoverable without losing bytes",async t=>{
  const h=await fixture(t);h.put("specs/a.md","authority");await h.connect();await h.local(".vibe/specs/a.md","unsaved");
  h.changes[0].hash="b".repeat(64);const invalid=new TeamMirror(h.root);assert.equal((await invalid.sync()).ok,false);
  assert.equal(await readFile(join(h.root,".vibe/specs/a.md"),"utf8"),"unsaved");assert.equal((await h.manifest()).cursor,0);
  h.changes[0].hash=hashContent("authority");const partial=new TeamMirror(h.root),write=partial.files.write.bind(partial.files);
  partial.files.write=async(path,bytes,expected)=>{if(path.endsWith("manifest.json"))throw new Error("injected disk failure");return write(path,bytes,expected);};
  assert.equal((await partial.sync()).ok,false);assert.equal((await h.manifest()).cursor,0);
  assert.equal((await new TeamMirror(h.root).sync()).ok,true);assert.equal((await h.manifest()).cursor,1);
  const copies=(await readdir(join(h.root,".vibe/specs"))).filter(name=>name.includes(".conflict-"));
  assert.ok(copies.length>=1);assert.equal(await readFile(join(h.root,".vibe/specs",copies[0]),"utf8"),"unsaved");
});

test("connection errors never establish binding and loose credential permissions stop sync",async t=>{
  const h=await fixture(t);h.denied(401);await assert.rejects(h.connect,/authentication_required/);assert.equal(await shouldEnableTeamModules(h.root),false);
  h.denied(0);await h.connect();const credentialPath=join(h.root,".vibe/.sync/credentials.json");
  if(process.platform!=="win32"){
    const {chmod}=await import("node:fs/promises");await chmod(credentialPath,0o644);const before=h.calls.length;
    assert.equal((await new TeamMirror(h.root).sync()).ok,false);assert.equal(h.calls.length,before);
  }
});

test("5xx uses the full 15/30/60/120 second backoff schedule without queueing work",async t=>{
  const h=await fixture(t);await h.connect();let clock=0;const mirror=new TeamMirror(h.root,{now:()=>clock});h.denied(503);
  assert.equal((await mirror.sync()).ok,false);
  for(const delay of [15000,30000,60000,120000,120000]) {
    const count=h.calls.length;clock+=delay-1;await mirror.sync();assert.equal(h.calls.length,count);
    clock++;await mirror.sync();assert.equal(h.calls.length,count+1);
  }
});

test("context reads only manifest-known work/progress, never activity, and stays under 2000 chars",async t=>{
  const h=await fixture(t);h.put("work/task.json",JSON.stringify({id:"t1",title:"x".repeat(3000),status:"claimed"}));
  h.put("members/owner/progress.md",`${"y".repeat(3000)}\nlast line`);h.put("activity/secret.md","DO NOT READ");
  await h.connect();const mirror=new TeamMirror(h.root);await mirror.sync();
  const reads:string[]=[],original=SafeFiles.prototype.read;
  SafeFiles.prototype.read=async function(path){reads.push(path);return original.call(this,path);};
  try {const text=await teamContext(h.root,mirror);assert.ok(text.length<=2000);assert.equal(text.includes("DO NOT READ"),false);assert.equal(reads.some(p=>p.includes("activity/")),false);}
  finally {SafeFiles.prototype.read=original;}
});
