import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdtemp, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { clearConflict, getConflict, listConflicts, recordConflict } from '../runtime/opencode/plugins/vibe-v2/team/conflicts.ts';

async function state(t: { after(fn: () => Promise<void>): void }) {
  const dir = await mkdtemp(join(tmpdir(), 'conf-'));
  t.after(() => rm(dir, { recursive: true, force: true }));
  return dir;
}
const base = { path: '.vibe/progress.md', kind: 'both_modified' as const, local: 'L1', remote: 'R1', baseVersion: 1, remoteVersion: 2 };

test('empty store lists nothing and reads null', async (t) => {
  const dir = await state(t);
  assert.deepEqual(await listConflicts(dir), []);
  assert.equal(await getConflict(dir, base.path), null);
});

test('record then list returns local and cloud content', async (t) => {
  const dir = await state(t);
  const saved = await recordConflict(dir, base, new Date('2026-11-27T00:00:00Z'));
  assert.equal(saved.createdAt, '2026-11-27T00:00:00.000Z');
  const all = await listConflicts(dir);
  assert.equal(all.length, 1);
  assert.equal(all[0].local, 'L1');
  assert.equal(all[0].remote, 'R1');
});

test('a repeated conflict keeps the earliest local content and refreshes only the cloud side', async (t) => {
  const dir = await state(t);
  await recordConflict(dir, base, new Date('2026-11-27T00:00:00Z'));
  const again = await recordConflict(dir, { ...base, local: 'L2', remote: 'R3', remoteVersion: 3 }, new Date('2026-11-28T00:00:00Z'));
  assert.equal(again.local, 'L1');
  assert.equal(again.remote, 'R3');
  assert.equal(again.remoteVersion, 3);
  assert.equal(again.createdAt, '2026-11-27T00:00:00.000Z');
  assert.equal((await listConflicts(dir)).length, 1);
});

test('deletion conflicts keep null sides; clear removes only that path and leaves no temp files', async (t) => {
  const dir = await state(t);
  await recordConflict(dir, { ...base, kind: 'remote_deleted_local_modified', remote: null });
  await recordConflict(dir, { ...base, path: '.vibe/docs/a.md', kind: 'local_deleted_remote_modified', local: null });
  assert.equal((await getConflict(dir, base.path))?.remote, null);
  await clearConflict(dir, base.path);
  const left = await listConflicts(dir);
  assert.deepEqual(left.map((c) => c.path), ['.vibe/docs/a.md']);
  assert.equal((await readdir(join(dir, 'conflicts'))).some((n) => n.startsWith('.tmp-')), false);
});
