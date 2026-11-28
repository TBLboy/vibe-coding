import assert from 'node:assert/strict';
import test from 'node:test';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdtemp, mkdir, readFile, realpath, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { once } from 'node:events';
import { connectWorkspace } from '../runtime/opencode/plugins/vibe-v2/team/binding.ts';
import { TeamMirror } from '../runtime/opencode/plugins/vibe-v2/team/mirror.ts';
import { listConflicts } from '../runtime/opencode/plugins/vibe-v2/team/conflicts.ts';
import { importWorkspace } from '../runtime/opencode/plugins/vibe-v2/team/import-workspace.ts';
import { TeamClient } from '../runtime/opencode/plugins/vibe-v2/team/client.ts';
import { clearDeviceBinding,stateDir,withStateLock,boundStateDir } from '../runtime/opencode/plugins/vibe-v2/team/device-state.ts';

// Real Workbench process (sibling worktree) + two independent plugin clients (V14).
const SERVER = resolve(import.meta.dirname, '..', '..', 'team-workspace-workbench', 'server', 'main.ts');
const ADMIN = 'e'.repeat(40);

test('two devices converge through a real Workbench: sync, conflict, delete', { timeout: 90000 }, async (t) => {
  assert.ok(existsSync(SERVER), 'the workbench worktree must sit next to this one: ' + SERVER);
  const base = await mkdtemp(join(tmpdir(), 'wb-e2e-'));
  const savedCfg = process.env.OPENCODE_CONFIG_DIR;
  process.env.OPENCODE_CONFIG_DIR = join(base, 'cfg');
  const child = spawn(process.execPath, ['--experimental-strip-types', SERVER], { env: { ...process.env, TEAM_DB_PATH: join(base, 'w.sqlite'), TEAM_PORT: '0', WORKBENCH_ADMIN_TOKEN: ADMIN }, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
  const exited = once(child, 'exit');
  t.after(async () => {
    if (child.exitCode === null) { child.kill(); await exited; }
    if (savedCfg === undefined) delete process.env.OPENCODE_CONFIG_DIR; else process.env.OPENCODE_CONFIG_DIR = savedCfg;
    await rm(base, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  });
  let out = '', err = '';
  child.stderr.on('data', (c) => { err += c; });
  const port = await new Promise<number>((res, rej) => {
    child.stdout.on('data', (c) => { out += c; for (const l of out.split('\n')) { try { const e = JSON.parse(l); if (e.event === 'listening') res(e.port); } catch { /* partial line */ } } });
    child.once('exit', (code) => rej(new Error('server exited ' + code + ': ' + err)));
  });
  const serverUrl = 'http://127.0.0.1:' + port;
  const created = await fetch(serverUrl + '/api/workspaces', { method: 'POST', headers: { authorization: 'Bearer ' + ADMIN, 'content-type': 'application/json' }, body: JSON.stringify({ name: 'E2E' }) });
  assert.equal(created.status, 201);
  const { key } = (await created.json()) as { key: string };

  const mk = async (name: string) => {
    const root = join(base, name);
    await mkdir(root);
    await connectWorkspace(root, { serverUrl, key });
    const file = (rel: string) => join(root, ...rel.split('/'));
    return {
      root, mirror: new TeamMirror(root, { budgetMs: 20000 }),
      read: (rel: string) => readFile(file(rel), 'utf8'),
      write: async (rel: string, text: string) => { await mkdir(join(file(rel), '..'), { recursive: true }); await writeFile(file(rel), text); },
      remove: (rel: string) => rm(file(rel)),
    };
  };
  const A = await mk('a'), B = await mk('b');

  const a1 = await A.mirror.sync(true);
  assert.equal(a1.ok, true, String(a1.lastError));
  assert.match(await A.read('AGENTS.md'), /VIBE-PROJECT-GENERAL/);
  const b1 = await B.mirror.sync(true);
  assert.equal(b1.ok, true, String(b1.lastError));
  assert.equal(await B.read('AGENTS.md'), await A.read('AGENTS.md'));

  // New remote blank initialization and the local published pack have identical bytes.
  const pack=JSON.parse(await readFile(resolve(import.meta.dirname,'../shared/team-contracts/templates/engineering-dev.json'),'utf8'));
  assert.equal(pack.version,3);
  for(const f of pack.files)assert.equal(await A.read(f.path),f.content);
  // Cross-device knowledge transport, not an assertion about Agent retrieval behavior.
  const memory = {
    '.vibe/lessons/README.md': '# Lessons\n| sync-retry | bug | active | retry, timeout | do not infer success |\n',
    '.vibe/lessons/sync-retry.md': '# Retry\nTrigger: timeout. Cause: unknown. Prevention: check actual state.\n',
    '.vibe/requirements/sync.md': '# Sync\nStatus: active. Verify first sync separately.\n',
    '.vibe/requirements/README.md': '# Requirements\n| sync | Sync | active | 1 | - |\n',
    '.vibe/sessions/ses_a/current-session.md': '# Recovery\nNext: verify local state.\n',
  };
  for(const [path,content] of Object.entries(memory))await A.write(path,content);
  assert.equal((await A.mirror.sync(true)).ok,true);
  assert.equal((await B.mirror.sync(true)).ok,true);
  for(const [path,content] of Object.entries(memory))assert.equal(await B.read(path),content);
  await A.remove('.vibe/sessions/ses_a/current-session.md');
  assert.equal((await A.mirror.sync(true)).ok,true);
  assert.equal((await B.mirror.sync(true)).ok,true);
  await assert.rejects(()=>B.read('.vibe/sessions/ses_a/current-session.md'));

  await A.write('.vibe/docs/x.md', 'from A');
  assert.equal((await A.mirror.sync(true)).ok, true);
  assert.equal((await B.mirror.sync(true)).ok, true);
  assert.equal(await B.read('.vibe/docs/x.md'), 'from A');

  await A.write('.vibe/progress.md', 'A edit');
  await B.write('.vibe/progress.md', 'B edit');
  assert.equal((await A.mirror.sync(true)).ok, true);
  const bc = await B.mirror.sync(true);
  assert.equal(bc.ok, true, String(bc.lastError));
  assert.equal(bc.conflicts, 1);
  assert.equal(await B.read('.vibe/progress.md'), 'A edit');
  const conflicts = await listConflicts(await boundStateDir(await realpath(B.root)));
  assert.equal(conflicts.length, 1);
  assert.equal(conflicts[0].local, 'B edit');
  const res = await B.mirror.resolveConflict('.vibe/progress.md', 'keep_local', undefined);
  assert.equal(res.status, 'resolved');
  assert.equal(await B.read('.vibe/progress.md'), 'B edit');
  assert.equal((await A.mirror.sync(true)).ok, true);
  assert.equal(await A.read('.vibe/progress.md'), 'B edit');

  await A.remove('.vibe/docs/x.md');
  assert.equal((await A.mirror.sync(true)).ok, true);
  assert.equal((await B.mirror.sync(true)).ok, true);
  await assert.rejects(() => B.read('.vibe/docs/x.md'));
  // Real HTTP and both clients preserve byte content, including NUL.
  const large='\0'.repeat(1024*1024-5)+'\ufeff\r\n';await A.write('.vibe/docs/large.md',large);assert.equal((await A.mirror.sync(true)).ok,true);assert.equal((await B.mirror.sync(true)).ok,true);assert.equal(await B.read('.vibe/docs/large.md'),large);
  // Lag behind >200 changes, including history pruning and deletion/recreation.
  const ws=(await new TeamClient(serverUrl,key).request('/connect','POST',{})).workspace.id;const client=new TeamClient(serverUrl,key);const path=`/workspaces/${ws}/documents/${encodeURIComponent('.vibe/docs/history.md')}`;
  let version=0;for(let i=0;i<205;i++){const r=await client.request(path,'PUT',{content:`history ${i}`},{'if-match':String(version)});version=r.version;}
  version=(await client.request(path,'DELETE',undefined,{'if-match':String(version)})).version;
  version=(await client.request(path,'PUT',{content:'recreated'},{'if-match':String(version)})).version;
  const before=B.mirror.status().cursor;assert.equal((await B.mirror.sync(true,undefined,60000)).ok,true);assert.equal(await B.read('.vibe/docs/history.md'),'recreated');assert.ok(B.mirror.status().cursor-before>200);assert.equal((await client.request(path)).version,version);
  assert.equal((await B.mirror.sync(true)).ok,true);assert.equal((await client.request(path)).version,version);
  // Import from an existing local root, bind a fresh root, compare bytes.
  const source=join(base,'import-source');await mkdir(join(source,'.vibe'),{recursive:true});await writeFile(join(source,'AGENTS.md'),'\ufeffimported\r\n');await writeFile(join(source,'.vibe/progress.md'),'progress\0');
  const imported=await importWorkspace(source,'Imported','engineering-dev',serverUrl,ADMIN);const target=join(base,'import-target');await mkdir(target);await connectWorkspace(target,{serverUrl,key:imported.key});const im=new TeamMirror(target);assert.equal((await im.sync(true)).ok,true);
  for(const rel of ['AGENTS.md','.vibe/progress.md'])assert.deepEqual(await readFile(join(source,rel)),await readFile(join(target,rel)));
  // Different workspace retains no previous cursor; rebind same workspace resumes its own cursor.
  const aState=await boundStateDir(A.root);const saved=await readFile(join(aState,'manifest.json'),'utf8');const dir=stateDir(A.root);
  await withStateLock(dir,()=>clearDeviceBinding(dir));await connectWorkspace(A.root,{serverUrl,key:imported.key});const bState=await boundStateDir(A.root);assert.notEqual(aState,bState);await assert.rejects(readFile(join(bState,'manifest.json')));
  await withStateLock(dir,()=>clearDeviceBinding(dir));await connectWorkspace(A.root,{serverUrl,key});assert.equal(await boundStateDir(A.root),aState);assert.equal(await readFile(join(aState,'manifest.json'),'utf8'),saved);
  assert.equal(out.includes(key), false);
  assert.equal(out.includes(ADMIN), false);
});
