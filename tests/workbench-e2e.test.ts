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
import { stateDir } from '../runtime/opencode/plugins/vibe-v2/team/device-state.ts';

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
  const conflicts = await listConflicts(stateDir(await realpath(B.root)));
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
  assert.equal(out.includes(key), false);
  assert.equal(out.includes(ADMIN), false);
});
