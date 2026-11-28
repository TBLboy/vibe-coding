import assert from 'node:assert/strict';import test from 'node:test';import http from 'node:http';import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';import {join} from 'node:path';import {tmpdir} from 'node:os';import type {AddressInfo} from 'node:net';import {importWorkspace} from '../runtime/opencode/plugins/vibe-v2/team/import-workspace.ts';

test('old endpoint fails safely; no fallback blank creation, invalid source never uploads',async t=>{
 const root=await mkdtemp(join(tmpdir(),'imp-refine-'));await mkdir(join(root,'.vibe'));await writeFile(join(root,'AGENTS.md'),'rules');await writeFile(join(root,'.vibe/progress.md'),'p');const calls:string[]=[];
 const server=http.createServer((req,res)=>{calls.push(req.url!);req.resume();res.writeHead(404,{'content-type':'application/json'});res.end('{}');});await new Promise<void>(r=>server.listen(0,'127.0.0.1',r));t.after(async()=>{server.closeAllConnections();server.close();await rm(root,{recursive:true,force:true});});
 const url='http://127.0.0.1:'+(server.address() as AddressInfo).port;await assert.rejects(importWorkspace(root,'Test','engineering-dev',url,'a'.repeat(40)));assert.deepEqual(calls,['/api/workspaces/import']);assert.equal(await readFile(join(root,'AGENTS.md'),'utf8'),'rules');
 await writeFile(join(root,'.vibe/binary'),Buffer.from([255]));await assert.rejects(importWorkspace(root,'Test','engineering-dev',url,'a'.repeat(40)),/import refused/);assert.equal(calls.length,1);
});
