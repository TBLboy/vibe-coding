import assert from 'node:assert/strict';
import test from 'node:test';
import { createHash } from 'node:crypto';
import { mkdir, mkdtemp, readFile, realpath, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createTaskController } from '../runtime/opencode/plugins/vibe-v2/task-control.ts';

const sha = (s: string): string => createHash('sha256').update(s).digest('hex');
const task = (over: Record<string, unknown> = {}) => ({ id: 't1', title: 'T', goal: 'G', doneWhen: ['d'], policy: 'balanced', status: 'active', phase: 'verify', decisions: ['keep'], verification: { status: 'passed', summary: 'ok', checks: ['c'], limitations: [], evidence: { root: '/x', paths: ['a'], digest: 'a'.repeat(64) } }, nextAction: 'n', ...over });

async function setup(t: { after(fn: () => Promise<void>): void }, record: Record<string, unknown>, opts: { hash?: string | null; noManifest?: boolean } = {}) {
  const root = await realpath(await mkdtemp(join(tmpdir(), 'adopt-')));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(join(root, '.vibe', 'tasks'), { recursive: true });
  const raw = JSON.stringify(record, null, 2) + '\n';
  const file = join(root, '.vibe', 'tasks', 't1.json');
  await writeFile(file, raw);
  const store = new Map<string, unknown>();
  const host: any = {
    storage: { get: async (k: string) => store.get(k), set: async (k: string, v: unknown) => { store.set(k, v); }, remove: async (k: string) => { store.delete(k); } },
    memoryRoot: async () => root, workspace: async () => root,
    childSession: async () => ({}), childContext: async () => [],
  };
  if (!opts.noManifest) host.syncedHash = async () => (opts.hash === undefined ? sha(raw) : opts.hash);
  const controller = createTaskController(host);
  const adopt = () => controller.control({ action: 'adopt', taskID: 't1' }, { sessionID: 's1', agent: 'vibe-main' });
  return { adopt, file, store };
}

test('adopt takes over an intact synced Task and voids old evidence', async (t) => {
  const h = await setup(t, task());
  assert.match(await h.adopt(), /adopted/);
  const saved = JSON.parse(await readFile(h.file, 'utf8'));
  assert.equal(saved.policy, 'balanced');
  assert.equal(saved.phase, 'implement');
  assert.equal(saved.verification.status, 'not_run');
  assert.equal(saved.verification.evidence, undefined);
  assert.deepEqual(saved.decisions, ['keep']);
  assert.equal(saved.nextAction, 'n');
});

test('adopt voids a pending strict review', async (t) => {
  const h = await setup(t, task({ policy: 'strict', phase: 'review', review: { verdict: 'pending', findings: [], repairRounds: 1 } }));
  await h.adopt();
  const saved = JSON.parse(await readFile(h.file, 'utf8'));
  assert.equal(saved.policy, 'strict');
  assert.equal(saved.phase, 'implement');
  assert.equal(saved.review.verdict, 'pending');
});

test('adopt is rejected for hash mismatch, untracked path, missing manifest, terminal and invalid Tasks', async (t) => {
  await assert.rejects((await setup(t, task(), { hash: 'f'.repeat(64) })).adopt(), /synced version/);
  await assert.rejects((await setup(t, task(), { hash: null })).adopt(), /synced version/);
  await assert.rejects((await setup(t, task(), { noManifest: true })).adopt(), /unavailable/);
  await assert.rejects((await setup(t, task({ status: 'completed', phase: 'complete' }))).adopt(), /Terminal/);
  await assert.rejects((await setup(t, task({ policy: 'nope' }))).adopt());
});
