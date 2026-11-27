import assert from 'node:assert/strict';
import test from 'node:test';
import http from 'node:http';
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { AddressInfo } from 'node:net';
import { hashContent } from '../shared/team-contracts/manifest.ts';
import { connectWorkspace } from '../runtime/opencode/plugins/vibe-v2/team/binding.ts';
import { TeamMirror } from '../runtime/opencode/plugins/vibe-v2/team/mirror.ts';
import { listConflicts } from '../runtime/opencode/plugins/vibe-v2/team/conflicts.ts';
import { stateDir } from '../runtime/opencode/plugins/vibe-v2/team/device-state.ts';

const KEY = 'K'.repeat(32);

async function fixture(t: { after(fn: () => Promise<void>): void }, options: { delayMs?: number } = {}) {
  const base = await mkdtemp(join(tmpdir(), 'mir-'));
  const saved = process.env.OPENCODE_CONFIG_DIR;
  process.env.OPENCODE_CONFIG_DIR = join(base, 'cfg');
  const root = join(base, 'proj');
  await mkdir(root);
  const docs = new Map<string, { version: number; content: string | null }>();
  const changes: any[] = [];
  let archived = false;
  const put = (path: string, content: string | null) => {
    const version = (docs.get(path)?.version ?? 0) + 1;
    docs.set(path, { version, content });
    changes.push({ seq: changes.length + 1, path, op: content === null ? 'delete' : 'upsert', version, ...(content === null ? {} : { hash: hashContent(content), content }) });
    return version;
  };
  const server = http.createServer((req, res) => {
    const url = new URL(req.url!, 'http://x');
    const send = (s: number, b: unknown) => { res.writeHead(s, { 'content-type': 'application/json' }); res.end(JSON.stringify(b)); };
    let body = '';
    req.on('data', (c) => { body += c; });
    req.on('end', () => {
      if (req.headers.authorization !== 'Bearer ' + KEY) return send(401, { error: {} });
      if (archived) return send(410, { error: { code: 'workspace_archived' } });
      const p = url.pathname, prefix = '/api/workspaces/ws_1/documents/';
      if (p === '/api/connect') return send(200, { workspace: { id: 'ws_1', name: 'W', type: 'engineering-dev' } });
      if (p === '/api/workspaces/ws_1/changes') {
        const since = Number(url.searchParams.get('since'));
        const reply = () => send(200, { changes: changes.filter((c) => c.seq > since), nextSeq: changes.length, hasMore: false });
        if (options.delayMs) setTimeout(reply, options.delayMs); else reply();
        return;
      }
      if (!p.startsWith(prefix)) return send(404, { error: {} });
      const path = decodeURIComponent(p.slice(prefix.length));
      const d = docs.get(path);
      if (req.method === 'GET') {
        if (!d) return send(404, { error: {} });
        return send(200, { path, version: d.version, hash: d.content === null ? null : hashContent(d.content), content: d.content });
      }
      const cur = d?.version ?? 0;
      if (Number(req.headers['if-match']) !== cur) return send(409, { error: { details: { currentVersion: cur } } });
      const content = req.method === 'DELETE' ? null : JSON.parse(body).content;
      const version = put(path, content);
      send(200, { version, hash: content === null ? null : hashContent(content) });
    });
  });
  await new Promise<void>((r) => server.listen(0, '127.0.0.1', r));
  t.after(async () => { server.closeAllConnections(); server.close(); if (saved === undefined) delete process.env.OPENCODE_CONFIG_DIR; else process.env.OPENCODE_CONFIG_DIR = saved; await rm(base, { recursive: true, force: true }); });
  const serverUrl = 'http://127.0.0.1:' + (server.address() as AddressInfo).port;
  await connectWorkspace(root, { serverUrl, key: KEY });
  const local = async (rel: string) => readFile(join(root, ...rel.split('/')), 'utf8');
  const write = async (rel: string, text: string) => { const f = join(root, ...rel.split('/')); await mkdir(join(f, '..'), { recursive: true }); await writeFile(f, text); };
  return { root, docs, put, local, write, setArchived: (v: boolean) => { archived = v; }, mirror: new TeamMirror(root, { budgetMs: 5000 }) };
}

test('first merge: cloud-only downloads, local-only uploads, nothing conflicts', async (t) => {
  const h = await fixture(t);
  h.put('AGENTS.md', 'cloud rules');
  h.put('.vibe/progress.md', 'p1');
  await h.write('.vibe/docs/local.md', 'mine');
  const r = await h.mirror.sync(true);
  assert.equal(r.ok, true, String(r.lastError));
  assert.equal(await h.local('AGENTS.md'), 'cloud rules');
  assert.equal(await h.local('.vibe/progress.md'), 'p1');
  assert.equal(h.docs.get('.vibe/docs/local.md')?.content, 'mine');
  assert.equal(r.conflicts, 0);
});

test('same path, different content: cloud lands on the path, local goes to the device conflict store', async (t) => {
  const h = await fixture(t);
  h.put('AGENTS.md', 'cloud');
  await h.write('AGENTS.md', 'local');
  const r = await h.mirror.sync(true);
  assert.equal(r.ok, true, String(r.lastError));
  assert.equal(await h.local('AGENTS.md'), 'cloud');
  const list = await listConflicts(stateDir(await (await import('node:fs/promises')).realpath(h.root)));
  assert.equal(list.length, 1);
  assert.equal(list[0].kind, 'both_modified');
  assert.equal(list[0].local, 'local');
  assert.equal(r.conflicts, 1);
  assert.deepEqual(await readdir(h.root), ['AGENTS.md']);
});

test('deletes propagate both ways', async (t) => {
  const h = await fixture(t);
  h.put('.vibe/docs/a.md', 'a');
  h.put('.vibe/docs/b.md', 'b');
  assert.equal((await h.mirror.sync(true)).ok, true);
  await rm(join(h.root, '.vibe', 'docs', 'a.md'));
  h.put('.vibe/docs/b.md', null);
  const r = await h.mirror.sync(true);
  assert.equal(r.ok, true, String(r.lastError));
  assert.equal(h.docs.get('.vibe/docs/a.md')?.content, null);
  await assert.rejects(() => h.local('.vibe/docs/b.md'));
  assert.equal(r.conflicts, 0);
});

test('an archived workspace (410) halts automatic sync until forced', async (t) => {
  const h = await fixture(t);
  h.put('AGENTS.md', 'x');
  assert.equal((await h.mirror.sync(true)).ok, true);
  h.setArchived(true);
  const r = await h.mirror.sync(true);
  assert.equal(r.ok, false);
  assert.equal(r.halted, 'workspace_archived');
  h.setArchived(false);
  assert.equal((await h.mirror.sync()).ok, false);
  assert.equal((await h.mirror.sync(true)).ok, true);
});

test('a slow server still syncs within the default budget', async (t) => {
  const h = await fixture(t, { delayMs: 2000 });
  h.put('AGENTS.md', 'slow cloud');
  const result = await new TeamMirror(h.root).sync(true);
  assert.equal(result.ok, true, String(result.lastError));
  assert.equal(await h.local('AGENTS.md'), 'slow cloud');
});
