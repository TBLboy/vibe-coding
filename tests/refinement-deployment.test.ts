import assert from 'node:assert/strict';
import test from 'node:test';
import {mkdtemp,rm,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {execFileSync} from 'node:child_process';
import {request} from 'node:https';
import type {AddressInfo} from 'node:net';
import {openTeamDatabase} from '../server/store/sqlite.ts';
import {createWorkspace} from '../server/domain/workspace.ts';
import {findWorkspaceByKey} from '../server/domain/key.ts';
import {getDocument} from '../server/domain/documents.ts';
import {getChanges} from '../server/domain/changes.ts';
import {createTeamServer} from '../server/http/router.ts';

test('refinement: live WAL consistent backup and isolated restore preserve workspace, key, bytes and cursor',async t=>{
 const dir=await mkdtemp(join(tmpdir(),'wb-backup-'));const store=openTeamDatabase(join(dir,'live.sqlite'));let restored:ReturnType<typeof openTeamDatabase>|undefined;t.after(async()=>{restored?.close();store.close();await rm(dir,{recursive:true,force:true});});
 const {workspace,key}=createWorkspace(store,{name:'fixture',type:'engineering-dev',files:[{path:'AGENTS.md',content:'\ufeffrules\0'},{path:'.vibe/progress.md',content:'p\r\n'}]},Date.now(),true);
 const dest=join(dir,'backup.sqlite');store.db.prepare('VACUUM INTO ?').run(dest);restored=openTeamDatabase(dest);
 assert.equal((restored.db.prepare('PRAGMA integrity_check').get() as any).integrity_check,'ok');assert.equal(findWorkspaceByKey(restored,key)?.workspaceId,workspace.id);assert.equal(getDocument(restored,{workspaceId:workspace.id,path:'AGENTS.md'})?.content,'\ufeffrules\0');assert.equal(getChanges(restored,{workspaceId:workspace.id,since:0}).nextSeq,2);
});

test('refinement: real HTTPS listener validates test certificate and keeps admin authorization',async t=>{
 const dir=await mkdtemp(join(tmpdir(),'wb-tls-'));const cert=join(dir,'cert.pem'),key=join(dir,'key.pem');
 try{execFileSync('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=localhost','-addext','subjectAltName=IP:127.0.0.1,DNS:localhost','-keyout',key,'-out',cert],{stdio:'ignore'});}catch(e){await rm(dir,{recursive:true,force:true});if((e as NodeJS.ErrnoException).code==='ENOENT'){t.skip('OpenSSL unavailable');return;}throw e;}
 const store=openTeamDatabase(':memory:'),admin='t'.repeat(40),server=createTeamServer(store,{adminToken:admin,tls:{cert,key}});await new Promise<void>(r=>server.listen(0,'127.0.0.1',r));t.after(async()=>{server.closeAllConnections();await new Promise<void>(r=>server.close(()=>r()));store.close();await rm(dir,{recursive:true,force:true});});
 const ca=await readFile(cert),port=(server.address() as AddressInfo).port;
 const call=(path:string,auth?:string)=>new Promise<number>((res,rej)=>{const req=request({hostname:'127.0.0.1',port,path,ca,headers:auth?{authorization:'Bearer '+auth}:{}},r=>{r.resume();r.on('end',()=>res(r.statusCode!));});req.on('error',rej);req.end();});
 assert.equal(await call('/api/healthz'),200);assert.equal(await call('/api/workspaces'),401);assert.equal(await call('/api/workspaces',admin),200);
});
