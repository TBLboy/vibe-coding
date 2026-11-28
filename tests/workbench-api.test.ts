import assert from 'node:assert/strict';
import test from 'node:test';
import type { AddressInfo } from 'node:net';
import { openTeamDatabase } from '../server/store/sqlite.ts';
import { createTeamServer } from '../server/http/router.ts';

const ADMIN = 'a'.repeat(40);

async function harness(t: { after(fn: () => void): void }) {
  const store = openTeamDatabase(':memory:');
  const server = createTeamServer(store, { adminToken: ADMIN });
  await new Promise<void>((r) => server.listen(0, '127.0.0.1', r));
  t.after(() => { server.closeAllConnections(); server.close(); store.close(); });
  const base = 'http://127.0.0.1:' + (server.address() as AddressInfo).port;
  const call = async (path: string, token: string | null, init: { method?: string; body?: unknown; headers?: Record<string, string> } = {}) => {
    const res = await fetch(base + path, {
      method: init.method ?? 'GET',
      headers: { ...(token ? { authorization: 'Bearer ' + token } : {}), ...(init.body !== undefined ? { 'content-type': 'application/json' } : {}), ...init.headers },
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    });
    return { status: res.status, json: (await res.json()) as any };
  };
  const create = async (name = 'W') => (await call('/api/workspaces', ADMIN, { method: 'POST', body: { name } })).json as { workspace: { id: string }; key: string };
  return { call, create };
}

test('admin routes: credentials, default type, unsupported type, Key is the wrong audience', async (t) => {
  const h = await harness(t);
  assert.equal((await h.call('/api/workspaces', null)).status, 401);
  assert.equal((await h.call('/api/workspaces', 'wrong')).status, 401);
  const c = await h.call('/api/workspaces', ADMIN, { method: 'POST', body: { name: 'W' } });
  assert.equal(c.status, 201);
  assert.equal(c.json.workspace.type, 'engineering-dev');
  const currentKey = await h.call('/api/workspaces/' + c.json.workspace.id + '/key', ADMIN);
  assert.equal(currentKey.status, 200);
  assert.equal(currentKey.json.key, c.json.key);
  assert.equal((await h.call('/api/workspaces', c.json.key)).status, 403);
  assert.equal((await h.call('/api/workspaces', ADMIN)).json.workspaces.length, 1);
  const bad = await h.call('/api/workspaces', ADMIN, { method: 'POST', body: { name: 'x', type: 'nope' } });
  assert.equal(bad.status, 422);
  assert.equal(bad.json.error.code, 'unsupported_type');
});

test('workspace routes: connect, template changes, If-Match, tombstone, path rules, Key isolation', async (t) => {
  const h = await harness(t);
  const { workspace, key } = await h.create();
  const ws = '/api/workspaces/' + workspace.id;
  assert.equal((await h.call('/api/connect', key, { method: 'POST' })).status, 200);
  assert.equal((await h.call(ws + '/changes?since=0', key)).json.changes.length, 6);
  const doc = ws + '/documents/.vibe/docs/a.md';
  const put = await h.call(doc, key, { method: 'PUT', body: { content: 'x' }, headers: { 'if-match': '0' } });
  assert.equal(put.status, 200);
  assert.equal(put.json.version, 1);
  const clash = await h.call(doc, key, { method: 'PUT', body: { content: 'y' }, headers: { 'if-match': '0' } });
  assert.equal(clash.status, 409);
  assert.equal(clash.json.error.details.currentVersion, 1);
  const priv = await h.call(ws + '/documents/.vibe/.sync/x.json', key, { method: 'PUT', body: { content: 'x' }, headers: { 'if-match': '0' } });
  assert.equal(priv.status, 422);
  const del = await h.call(doc, key, { method: 'DELETE', headers: { 'if-match': '1' } });
  assert.equal(del.status, 200);
  assert.equal(del.json.version, 2);
  assert.equal((await h.call(doc, key)).json.content, null);
  const other = await h.create('Other');
  assert.equal((await h.call(ws + '/changes?since=0', other.key)).status, 403);
});

test('archive: Key stops working with 410 and the space leaves the list', async (t) => {
  const h = await harness(t);
  const { workspace, key } = await h.create();
  assert.equal((await h.call('/api/workspaces/' + workspace.id, ADMIN, { method: 'DELETE' })).status, 200);
  const res = await h.call('/api/connect', key, { method: 'POST' });
  assert.equal(res.status, 410);
  assert.equal(res.json.error.code, 'workspace_archived');
  assert.equal((await h.call('/api/workspaces', ADMIN)).json.workspaces.length, 0);
  assert.equal((await h.call('/api/workspaces/' + workspace.id + '/key', ADMIN)).status, 404);
});


test('refinement: exact UTF-8 including worst JSON expansion, BOM, CRLF and NUL; route limits and early auth',async t=>{
 const h=await harness(t);const {workspace,key}=await h.create();const prefix='/api/workspaces/'+workspace.id;
 const content='\0'.repeat(1024*1024-5)+'\ufeff\r\n';const path=prefix+'/documents/.vibe/docs/large.md';
 const put=await h.call(path,key,{method:'PUT',headers:{'if-match':'0'},body:{content}});assert.equal(put.status,200);
 assert.equal((await h.call(path,key)).json.content,content);
 const changes=await h.call(prefix+'/changes?since=0',key);assert.equal(changes.status,200);assert.equal(changes.json.changes.at(-1).content,content);
 assert.equal((await h.call(path,key,{method:'PUT',headers:{'if-match':'1'},body:{content:content+'x'}})).status,413);
 assert.equal((await h.call(path,key,{method:'PUT',headers:{'if-match':'1'},body:{content:'\ud800'}})).status,422);
 assert.equal((await h.call(path,null,{method:'PUT',headers:{'if-match':'1'},body:{content}})).status,401);
 assert.equal((await h.call('/api/workspaces',ADMIN,{method:'POST',body:{name:'x',padding:content}})).status,413);
});

test('refinement: import permissions, exact source files, rejection without new workspace',async t=>{
 const h=await harness(t);const {key}=await h.create();const files=[{path:'AGENTS.md',content:'\ufeffrules\r\n'},{path:'.vibe/progress.md',content:'progress\0'},{path:'.vibe/docs/empty.md',content:''}];const payload={name:'Imported',type:'engineering-dev',files};
 assert.equal((await h.call('/api/workspaces/import',null,{method:'POST',body:payload})).status,401);
 assert.equal((await h.call('/api/workspaces/import',key,{method:'POST',body:payload})).status,403);
 const r=await h.call('/api/workspaces/import',ADMIN,{method:'POST',body:payload});assert.equal(r.status,201);
 const feed=(await h.call('/api/workspaces/'+r.json.workspace.id+'/changes?since=0',r.json.key)).json.changes;
 assert.deepEqual(feed.map((x:any)=>({path:x.path,content:x.content})),files);
 for(const invalidFiles of [[files[0]],[...files,files[0]],[...files,{path:'.vibe/.SYNC/a',content:'x'}],[...files,{path:'.vibe/docs/CON.txt',content:'x'}],[...files,{path:'.vibe/docs/EMPTY.md',content:'x'}],[...files,{path:'.vibe/docs/empty.md/x',content:'x'}],[...files,{path:'.vibe/docs/large',content:'x'.repeat(1048577)}]]){
  const bad=await h.call('/api/workspaces/import',ADMIN,{method:'POST',body:{...payload,files:invalidFiles}});assert.ok([422,413].includes(bad.status),String(bad.status));
 }
 assert.equal((await h.call('/api/workspaces',ADMIN)).json.workspaces.length,2);
});
