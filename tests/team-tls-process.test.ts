import assert from "node:assert/strict";
import test, { type TestContext } from "node:test";
import { fork, execFile } from "node:child_process";
import { promisify } from "node:util";
import { mkdtemp, mkdir, readFile, writeFile, rm, stat, readdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { createServer as createHttpsServer } from "node:https";
import { request, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { randomBytes } from "node:crypto";
import { openTeamDatabase } from "../server/store/sqlite.ts";
import { createAccount } from "../server/domain/identity.ts";
import { createTeamServer, type RequestLog } from "../server/http/router.ts";
import { hashContent } from "../runtime/core/team/manifest.ts";

const exec=promisify(execFile);
async function fixture(t:TestContext,count=2) {
  const base=await mkdtemp(join(tmpdir(),"team-tls-process-"));
  const store=openTeamDatabase(join(base,"workspace.sqlite")),logs:RequestLog[]=[];
  let server:Server|undefined;
  t.after(async()=>{
    if(server){server.closeAllConnections();await new Promise<void>(r=>server!.close(()=>r()));}
    store.close();await rm(base,{recursive:true,force:true});
  });
  const password=randomBytes(24).toString("base64url"),orgId="org_transport",accounts=[];
  for(let i=0;i<count;i++)accounts.push(await createAccount(store,{orgId,email:`writer${i}@example.test`,displayName:`Writer ${i}`,password}));
  server=createTeamServer(store,{orgId,logger:entry=>logs.push(entry)});
  await new Promise<void>(r=>server!.listen(0,"127.0.0.1",r));
  const url=`http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  const req=async(path:string,method="GET",token?:string,body?:unknown)=>{
    const response=await fetch(url+path,{method,headers:{...(token?{authorization:`Bearer ${token}`} : {}),...(body===undefined?{}:{"content-type":"application/json"})},...(body===undefined?{}:{body:JSON.stringify(body)})});
    return {status:response.status,body:await response.json() as any};
  };
  const sessions=[];
  for(const account of accounts){const r=await req("/api/auth/login","POST",undefined,{email:account.email,password});assert.equal(r.status,200);sessions.push(r.body.sessionToken);}
  const created=await req("/api/workspaces","POST",sessions[0],{name:"Transport test",repos:[{url:"https://example.test/project.git",branch:"main"}]});
  assert.equal(created.status,201);const key=created.body.taskKey,id=created.body.workspace.id,p=`/api/workspaces/${id}`;
  const connected=await req("/api/connect","POST",sessions[0],{key});assert.equal(connected.status,200);const token=connected.body.workspaceToken;
  for(let i=1;i<count;i++){
    assert.equal((await req(`${p}/invitations`,"POST",token,{email:accounts[i].email})).status,201);
    assert.equal((await req(`${p}/invitations/accept`,"POST",sessions[i],{})).status,200);
  }
  const roots=[];for(let i=0;i<count;i++){const root=join(base,`client${i}`);await mkdir(root,{mode:0o700});roots.push(root);}
  const manifest=async(i:number)=>JSON.parse(await readFile(join(roots[i],".vibe/.sync/manifest.json"),"utf8"));
  return {base,store,logs,accounts,password,sessions,key,id,p,token,url,roots,req,manifest};
}

async function certificates(base:string) {
  const dir=join(base,"tls");await mkdir(dir,{mode:0o700});
  const run=(args:string[])=>exec("openssl",args,{cwd:dir,windowsHide:true,timeout:15000});
  await run(["req","-x509","-newkey","rsa:2048","-nodes","-keyout","ca.key","-out","ca.pem","-days","1","-subj","/CN=Ephemeral team test CA"]);
  for(const name of ["valid","wrong-host"]){
    await run(["req","-new","-newkey","rsa:2048","-nodes","-keyout",`${name}.key`,"-out",`${name}.csr`,"-subj",`/CN=${name}`]);
    await writeFile(join(dir,`${name}.ext`),`basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=${name==="valid"?"IP:127.0.0.1":"DNS:wrong-host.invalid"}\n`);
    await run(["x509","-req","-in",`${name}.csr`,"-CA","ca.pem","-CAkey","ca.key","-set_serial",name==="valid"?"2":"3","-out",`${name}.pem`,"-days","1","-extfile",`${name}.ext`]);
  }
  return {dir,ca:join(dir,"ca.pem")};
}

async function proxy(t:TestContext,target:string,dir:string,name="valid") {
  const hits:{method:string;path:string;encrypted:boolean}[]=[];
  const server=createHttpsServer({key:await readFile(join(dir,`${name}.key`)),cert:await readFile(join(dir,`${name}.pem`))},(req,res)=>{
    hits.push({method:req.method!,path:req.url!,encrypted:!!(req.socket as {encrypted?:boolean}).encrypted});
    const upstream=request(new URL(req.url!,target),{method:req.method,headers:{...req.headers,host:new URL(target).host}},response=>{
      res.writeHead(response.statusCode!,response.headers);response.pipe(res);
    });
    upstream.on("error",()=>{if(!res.headersSent)res.writeHead(502);res.end();});
    req.on("aborted",()=>upstream.destroy());req.pipe(upstream);
  });
  await new Promise<void>(r=>server.listen(0,"127.0.0.1",r));
  t.after(async()=>{server.closeAllConnections();await new Promise<void>(r=>server.close(()=>r()));});
  return {url:`https://127.0.0.1:${(server.address() as AddressInfo).port}`,hits};
}

async function worker(t:TestContext,ca?:string) {
  const env={...process.env};
  // A test must not inherit insecure or machine-specific Node transport overrides.
  for(const key of ["NODE_TLS_REJECT_UNAUTHORIZED","NODE_OPTIONS","NODE_EXTRA_CA_CERTS","SSL_CERT_FILE","SSL_CERT_DIR"])delete env[key];
  if(ca)env.NODE_EXTRA_CA_CERTS=ca;
  const child=fork(resolve("tests/helpers/team-acceptance-worker.ts"),[],{execArgv:["--experimental-strip-types"],env,stdio:["ignore","pipe","pipe","ipc"],windowsHide:true});
  let stdout="",stderr="",next=0;
  child.stdout!.on("data",bytes=>{stdout+=bytes;});child.stderr!.on("data",bytes=>{stderr+=bytes;});
  const pending=new Map<number,{resolve:(value:any)=>void;reject:(e:Error)=>void;timer:ReturnType<typeof setTimeout>}>();
  const exited=new Promise<number|null>(r=>child.once("exit",r));
  child.on("exit",()=>{for(const call of pending.values()){clearTimeout(call.timer);call.reject(new Error("worker exited before reply"));}pending.clear();});
  t.after(async()=>{if(child.exitCode===null&&child.signalCode===null)child.kill();await exited;});
  await new Promise<void>((r,j)=>{
    const timer=setTimeout(()=>j(new Error("worker readiness timeout")),10000);
    child.once("error",error=>{clearTimeout(timer);j(error);});
    child.on("message",(message:any)=>{
      if(message.ready){clearTimeout(timer);r();return;}
      const call=pending.get(message.id);if(!call)return;clearTimeout(call.timer);pending.delete(message.id);call.resolve(message);
    });
  });
  const call=(input:Record<string,unknown>)=>new Promise<any>((r,j)=>{
    const id=next++,timer=setTimeout(()=>{pending.delete(id);j(new Error("worker operation timeout"));},10000);
    pending.set(id,{resolve:r,reject:j,timer});child.send({...input,id});
  });
  return {pid:child.pid,call,output:()=>stdout+stderr,stop:async()=>{child.send({action:"stop"});assert.equal(await exited,0);}};
}

test("verified TLS proxy: actual plugin login/connect/pull/push and HTTP auth rejection",{timeout:30000},async t=>{
  const h=await fixture(t),tls=await certificates(h.base),front=await proxy(t,h.url,tls.dir),client=await worker(t,tls.ca);
  const connected=await client.call({action:"connect",url:front.url,root:h.roots[1],email:h.accounts[1].email,password:h.password,key:h.key});
  assert.equal(connected.ok,true);assert.equal(connected.result.accountId,h.accounts[1].id);assert.equal(connected.result.sync.ok,true);
  const credentials=JSON.parse(await readFile(join(h.roots[1],".vibe/.sync/credentials.json"),"utf8"));
  assert.equal(credentials.serverUrl,front.url);assert.equal((await h.manifest(1)).cursor,1);
  const pushed=await client.call({action:"append",text:"TLS verified progress"});assert.equal(pushed.ok,true);assert.equal(pushed.result.status,"synced");
  const path=`members/${h.accounts[1].id}/progress.md`,doc=await h.req(`${h.p}/documents/${path}`,"GET",h.token);
  assert.equal(doc.status,200);assert.match(doc.body.content,/TLS verified progress/);assert.equal(doc.body.version,1);
  assert.equal(await readFile(join(h.roots[1],".vibe",path),"utf8"),doc.body.content);
  const manifest=await h.manifest(1);assert.equal(manifest.cursor,2);assert.equal(manifest.entries[path].hash,hashContent(doc.body.content));
  assert.ok(front.hits.some(x=>x.path==="/api/auth/login"));assert.ok(front.hits.some(x=>x.path==="/api/connect"));
  assert.ok(front.hits.some(x=>x.method==="PUT"));assert.ok(front.hits.every(x=>x.encrypted));
  const before=h.store.db.prepare("SELECT count(*) AS n FROM change").get()!.n;
  const denied=await client.call({action:"bind",url:front.url,root:h.roots[0],sessionToken:h.sessions[0],key:"x".repeat(32)});
  assert.equal(denied.ok,false);assert.equal(denied.error,"authentication_required");assert.equal(denied.status,401);
  const deniedToken=await client.call({action:"metadata",url:front.url,workspaceId:h.id,token:"x".repeat(43)});
  assert.equal(deniedToken.ok,false);assert.equal(deniedToken.error,"authentication_required");assert.equal(deniedToken.status,401);
  await assert.rejects(()=>stat(join(h.roots[0],".vibe/.sync/binding.json")),/ENOENT/);
  assert.equal(h.store.db.prepare("SELECT count(*) AS n FROM change").get()!.n,before);
  if(process.platform!=="win32"){
    assert.equal((await stat(join(h.roots[1],".vibe/.sync/credentials.json"))).mode&0o777,0o600);
    assert.equal((await stat(join(tls.dir,"valid.key"))).mode&0o777,0o600);
    assert.equal((await stat(join(tls.dir,"ca.key"))).mode&0o777,0o600);
  }
  for(const secret of [h.password,h.key,credentials.workspaceToken,...h.sessions])assert.equal((client.output()+JSON.stringify(h.logs)).includes(secret),false);
  await client.stop();
});

test("untrusted chain and trusted wrong-host certificate reject plugin traffic before HTTP",{timeout:30000},async t=>{
  const h=await fixture(t),tls=await certificates(h.base),valid=await proxy(t,h.url,tls.dir),wrong=await proxy(t,h.url,tls.dir,"wrong-host");
  for(const [front,ca,expected] of [[valid,undefined,/UNABLE_TO_VERIFY_LEAF_SIGNATURE|UNABLE_TO_GET_ISSUER_CERT_LOCALLY|SELF_SIGNED_CERT_IN_CHAIN/],[wrong,tls.ca,/ERR_TLS_CERT_ALTNAME_INVALID/]] as const){
    const client=await worker(t,ca),before=h.logs.length;
    const probe=await client.call({action:"probe",url:front.url,email:h.accounts[0].email,password:h.password});
    assert.equal(probe.ok,true);assert.equal(probe.result.clientError,"network_unavailable");assert.match(probe.result.tlsError,expected);
    const denied=await client.call({action:"bind",url:front.url,root:h.roots[0],sessionToken:h.sessions[0],key:h.key});
    assert.equal(denied.ok,false);assert.equal(denied.error,"network_unavailable");
    assert.equal(front.hits.length,0);assert.equal(h.logs.length,before);
    await assert.rejects(()=>stat(join(h.roots[0],".vibe/.sync/binding.json")),/ENOENT/);
    assert.equal(h.store.db.prepare("SELECT seq FROM workspace_seq WHERE workspace_id=?").get(h.id)!.seq,1);
    await client.stop();
  }
});

test("four independent plugin processes write 12 updates over verified TLS and converge",{timeout:30000},async t=>{
  const h=await fixture(t,4),tls=await certificates(h.base),front=await proxy(t,h.url,tls.dir);
  const clients=await Promise.all(h.roots.map(()=>worker(t,tls.ca)));
  assert.equal(new Set(clients.map(c=>c.pid)).size,4);
  const connected=await Promise.all(clients.map((c,i)=>c.call({action:"connect",url:front.url,root:h.roots[i],email:h.accounts[i].email,password:h.password,key:h.key})));
  for(const reply of connected){assert.equal(reply.ok,true);assert.equal(reply.result.sync.ok,true);}
  const cursors=connected.map(reply=>reply.result.sync.cursor);
  for(let round=0;round<3;round++){
    const results=await Promise.all(clients.map((client,i)=>client.call({action:"append",text:`writer=${i};round=${round}`})));
    for(let i=0;i<results.length;i++){
      const reply=results[i];assert.equal(reply.ok,true);assert.equal(reply.result.status,"synced");
      assert.ok(reply.result.cursor>=cursors[i]);assert.ok(reply.result.cursor<=1+4*(round+1));cursors[i]=reply.result.cursor;
    }
  }
  const head=(await h.req(h.p,"GET",h.token)).body.workspace.seq;assert.equal(head,13);
  const synced=await Promise.all(clients.map(client=>client.call({action:"sync"})));
  for(const reply of synced){assert.equal(reply.ok,true);assert.equal(reply.result.ok,true);assert.equal(reply.result.cursor,head);}
  const feed=(await h.req(`${h.p}/changes?since=0`,"GET",h.token)).body;
  assert.deepEqual(feed.changes.map((c:any)=>c.seq),Array.from({length:13},(_,i)=>i+1));
  assert.equal(h.logs.filter(x=>x.route==="documents.put").length,12);assert.equal(h.logs.some(x=>x.status===409),false);
  assert.equal(front.hits.filter(x=>x.method==="PUT").length,12);assert.ok(front.hits.every(x=>x.encrypted));
  for(let i=0;i<4;i++){
    const path=`members/${h.accounts[i].id}/progress.md`,doc=(await h.req(`${h.p}/documents/${path}`,"GET",h.token)).body;
    assert.equal(doc.version,3);for(let round=0;round<3;round++)assert.equal(doc.content.split(`writer=${i};round=${round}`).length-1,1);
    for(let other=0;other<4;other++)if(other!==i)assert.equal(doc.content.includes(`writer=${other};`),false);
    assert.equal(feed.changes.filter((c:any)=>c.path===path).length,3);
    for(let j=0;j<4;j++){
      const manifest=await h.manifest(j);assert.equal(manifest.cursor,head);assert.equal(Object.keys(manifest.entries).length,5);
      assert.equal(manifest.entries[path].version,3);assert.equal(manifest.entries[path].hash,doc.hash);
      assert.equal(hashContent(await readFile(join(h.roots[j],".vibe",path))),doc.hash);
      assert.equal(await readFile(join(h.roots[j],".vibe",path),"utf8"),doc.content);
    }
  }
  assert.equal(h.store.db.prepare("SELECT count(*) AS n FROM document_version").get()!.n,13);
  assert.equal(h.store.db.prepare("SELECT count(*) AS n FROM document").get()!.n,5);
  for(let i=0;i<4;i++){
    const names=await readdir(join(h.roots[i],".vibe/.sync"));assert.equal(names.some(n=>n.includes("lock")||n.includes(".tmp-")),false);
    const credentials=JSON.parse(await readFile(join(h.roots[i],".vibe/.sync/credentials.json"),"utf8"));
    for(const secret of [h.password,h.key,credentials.workspaceToken,...h.sessions])assert.equal((clients.map(c=>c.output()).join("")+JSON.stringify(h.logs)).includes(secret),false);
  }
  await Promise.all(clients.map(client=>client.stop()));
});
