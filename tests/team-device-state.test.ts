import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdtemp, readdir, rm, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { clearDeviceBinding, loadDeviceBinding, loadKey, saveDeviceBinding, saveKey, stateDir, validateDeviceBinding } from '../runtime/opencode/plugins/vibe-v2/team/device-state.ts';

const KEY = 'A'.repeat(32);
const B = { workspaceId: 'ws_1', workspaceType: 'engineering-dev', serverUrl: 'https://wb.example.test:7410/' };

test('state dir is outside the project and derived from the real root', () => {
  const env = { OPENCODE_CONFIG_DIR: join(tmpdir(), 'cfg') };
  const a = stateDir('/work/a', env), b = stateDir('/work/b', env);
  assert.notEqual(a, b);
  assert.ok(a.startsWith(join(tmpdir(), 'cfg', 'vibe-worklog')));
  assert.equal(stateDir('/work/a', env), a);
});

test('binding round-trips with normalized url; key stays separate and validated', async (t) => {
  const dir = join(await mkdtemp(join(tmpdir(), 'dev-state-')), 's');
  t.after(() => rm(join(dir, '..'), { recursive: true, force: true }));
  assert.equal(await loadDeviceBinding(dir), null);
  await saveDeviceBinding(dir, B);
  assert.deepEqual(await loadDeviceBinding(dir), { ...B, serverUrl: 'https://wb.example.test:7410' });
  await saveKey(dir, KEY);
  assert.equal(await loadKey(dir), KEY);
  assert.deepEqual((await readdir(dir)).sort(), ['binding.json', 'credentials.json']);
  if (process.platform !== 'win32') assert.equal((await stat(join(dir, 'credentials.json'))).mode & 0o077, 0);
  await assert.rejects(() => saveKey(dir, 'short'), /invalid key/);
});

test('invalid bindings are rejected and disconnect keeps other state', async (t) => {
  const dir = join(await mkdtemp(join(tmpdir(), 'dev-state-')), 's');
  t.after(() => rm(join(dir, '..'), { recursive: true, force: true }));
  for (const bad of [null, [], { ...B, workspaceId: '../x' }, { ...B, workspaceType: 'Bad Type' }, { ...B, serverUrl: 'ftp://x' }, { ...B, serverUrl: 'https://u:p@x' }, { ...B, serverUrl: 'https://x/?a=1' }]) {
    assert.throws(() => validateDeviceBinding(bad));
  }
  await saveDeviceBinding(dir, B); await saveKey(dir, KEY);
  await clearDeviceBinding(dir);
  assert.equal(await loadDeviceBinding(dir), null);
  assert.equal(await loadKey(dir), null);
});
