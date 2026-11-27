import assert from 'node:assert/strict';
import test from 'node:test';
import { planPull, planPush } from '../runtime/opencode/plugins/vibe-v2/team/sync-plan.ts';

const E = { version: 3, hash: 'a' };

test('push: new, unchanged, modified, deleted, absent', () => {
  assert.deepEqual(planPush(undefined, 'x'), { action: 'push', baseVersion: 0 });
  assert.deepEqual(planPush(undefined, null), { action: 'noop' });
  assert.deepEqual(planPush(E, 'a'), { action: 'noop' });
  assert.deepEqual(planPush(E, 'b'), { action: 'push', baseVersion: 3 });
  assert.deepEqual(planPush(E, null), { action: 'pushDelete', baseVersion: 3 });
});

test('pull: equal content adopts, untouched local applies cloud (including deletion)', () => {
  assert.deepEqual(planPull(E, 'b', 'b'), { action: 'adopt' });
  assert.deepEqual(planPull(E, null, null), { action: 'adopt' });
  assert.deepEqual(planPull(E, 'a', 'b'), { action: 'apply' });
  assert.deepEqual(planPull(E, 'a', null), { action: 'apply' });
  assert.deepEqual(planPull(undefined, null, 'b'), { action: 'apply' });
});

test('pull: unsynced local changes never get overwritten; they become typed conflicts', () => {
  assert.deepEqual(planPull(E, 'c', 'b'), { action: 'conflict', kind: 'both_modified' });
  assert.deepEqual(planPull(E, 'c', null), { action: 'conflict', kind: 'remote_deleted_local_modified' });
  assert.deepEqual(planPull(E, null, 'b'), { action: 'conflict', kind: 'local_deleted_remote_modified' });
  assert.deepEqual(planPull(undefined, 'c', 'b'), { action: 'conflict', kind: 'both_modified' });
});
