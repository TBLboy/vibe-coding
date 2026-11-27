import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { scanSyncFiles } from '../runtime/opencode/plugins/vibe-v2/team/scan.ts';

async function fixture(t: { after(fn: () => Promise<void>): void }) {
  const root = await mkdtemp(join(tmpdir(), 'scan-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  return root;
}
const put = async (root: string, rel: string, data: string | Uint8Array) => {
  const full = join(root, ...rel.split('/'));
  await mkdir(join(full, '..'), { recursive: true });
  await writeFile(full, data);
};

test('scope is AGENTS.md plus all files under .vibe/, any depth, sorted', async (t) => {
  const root = await fixture(t);
  await put(root, 'AGENTS.md', 'rules');
  await put(root, '.vibe/progress.md', 'p');
  await put(root, '.vibe/lessons/a/b.md', 'l');
  await put(root, '.vibe/tasks/.gitkeep', '');
  await put(root, 'src/app.ts', 'not synced');
  await put(root, 'README.md', 'not synced');
  const result = await scanSyncFiles(root);
  assert.deepEqual(result.files, ['.vibe/lessons/a/b.md', '.vibe/progress.md', '.vibe/tasks/.gitkeep', 'AGENTS.md']);
  assert.deepEqual(result.warnings, []);
});

test('device-private .vibe/.sync and temp files are excluded silently', async (t) => {
  const root = await fixture(t);
  await put(root, '.vibe/.sync/manifest.json', '{}');
  await put(root, '.vibe/docs/.tmp-123', 'x');
  await put(root, '.vibe/docs/a.md', 'a');
  const result = await scanSyncFiles(root);
  assert.deepEqual(result.files, ['.vibe/docs/a.md']);
  assert.deepEqual(result.warnings, []);
});

test('oversized and non-UTF-8 files are skipped with a warning without aborting the round', async (t) => {
  const root = await fixture(t);
  await put(root, '.vibe/docs/ok.md', 'ok');
  await put(root, '.vibe/docs/big.md', Buffer.alloc(1024 * 1024 + 1, 97));
  await put(root, '.vibe/docs/edge.md', Buffer.alloc(1024 * 1024, 97));
  await put(root, '.vibe/docs/bin.dat', Uint8Array.from([0xff, 0xfe, 0x00, 0x80]));
  const result = await scanSyncFiles(root);
  assert.deepEqual(result.files, ['.vibe/docs/edge.md', '.vibe/docs/ok.md']);
  assert.equal(result.warnings.length, 2);
  assert.ok(result.warnings.some((w) => w.includes('big.md') && w.includes('1 MiB')));
  assert.ok(result.warnings.some((w) => w.includes('bin.dat') && w.includes('UTF-8')));
});

test('a project with no .vibe and no AGENTS.md scans to an empty result', async (t) => {
  const root = await fixture(t);
  assert.deepEqual(await scanSyncFiles(root), { files: [], warnings: [] });
});
